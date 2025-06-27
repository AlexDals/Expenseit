# File: utils/supabase_utils.py

import streamlit as st
from supabase import create_client, Client
import pandas as pd
from datetime import datetime
import os
import json
import xml.etree.ElementTree as ET
from xml.dom import minidom

@st.cache_resource
def init_connection() -> Client:
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key)
    except KeyError:
        st.error("Supabase credentials not found.")
        st.stop()

def get_single_user_details(user_id: str):
    """Fetches all details for a single user to populate the edit form."""
    supabase = init_connection()
    try:
        resp = (
            supabase
            .table("users")
            .select("id, username, name, email, role, approver_id, default_category_id")
            .eq("id", user_id)
            .maybe_single()
            .execute()
        )
        return resp.data
    except Exception as e:
        st.error(f"Error fetching user details: {e}")
        return None

def fetch_all_users_for_auth():
    supabase = init_connection()
    try:
        resp = supabase.table("users").select(
            "id, username, email, name, hashed_password, role"
        ).execute()
        users_data = resp.data
        credentials = {"usernames": {}}
        for u in users_data:
            credentials["usernames"][u["username"]] = {
                "id":       u["id"],
                "email":    u["email"],
                "name":     u["name"],
                "password": u["hashed_password"],
                "role":     u["role"],
            }
        return credentials
    except Exception as e:
        st.error(f"Error fetching users: {e}")
        return {"usernames": {}}

def register_user(username, name, email, hashed_password, role="user"):
    supabase = init_connection()
    try:
        if not all([username, name, email, hashed_password, role]):
            st.error("All fields are required for registration.")
            return False
        if supabase.table("users").select("id", count="exact").eq("username", username).execute().count > 0:
            st.error(f"Username '{username}' already taken.")
            return False
        supabase.table("users").insert({
            "username": username,
            "name":     name,
            "email":    email,
            "hashed_password": hashed_password,
            "role":     role
        }).execute()
        return True
    except Exception as e:
        st.error(f"Error during registration: {e}")
        return False

def get_user_role(username: str):
    supabase = init_connection()
    try:
        resp = supabase.table("users").select("role").eq("username", username).execute()
        return resp.data[0].get("role") if resp.data else None
    except Exception as e:
        st.error(f"Error fetching user role: {e}")
        return None

def get_all_users():
    supabase = init_connection()
    try:
        resp = supabase.table("users").select(
            "id, username, name, email, role, approver_id, default_category:categories(id, name)"
        ).execute()
        users = resp.data
        for user in users:
            cat = user.pop("default_category", None)
            if isinstance(cat, dict):
                user["default_category_id"]   = cat.get("id")
                user["default_category_name"] = cat.get("name")
            else:
                user["default_category_id"]   = None
                user["default_category_name"] = None
        return pd.DataFrame(users)
    except Exception as e:
        st.error(f"Error fetching all users: {e}")
        return pd.DataFrame()

def get_all_approvers():
    supabase = init_connection()
    try:
        resp = supabase.table("users").select("id, name").in_("role", ["approver", "admin"]).execute()
        return resp.data
    except Exception as e:
        st.error(f"Error fetching approvers: {e}")
        return []

def update_user_details(user_id, role, approver_id, default_category_id):
    supabase = init_connection()
    try:
        supabase.table("users").update({
            "role":                role,
            "approver_id":         approver_id,
            "default_category_id": default_category_id
        }).eq("id", user_id).execute()
        return True
    except Exception as e:
        st.error(f"Error updating user details: {e}")
        return False

def delete_user(user_id):
    supabase = init_connection()
    try:
        supabase.table("users").delete().eq("id", user_id).execute()
        return True
    except Exception as e:
        st.error(f"Error deleting user: {e}")
        return False

def add_report(user_id, report_name, total_amount):
    supabase = init_connection()
    try:
        resp = supabase.table("reports").insert({
            "user_id":         user_id,
            "report_name":     report_name,
            "submission_date": datetime.now().isoformat(),
            "total_amount":    total_amount,
            "status":          "Submitted"
        }).execute()
        return resp.data[0]["id"] if resp.data else None
    except Exception as e:
        st.error(f"Error adding report: {e}")
        return None

def add_expense_item(
    report_id,
    expense_date,
    vendor,
    description,
    amount,
    currency="CAD",
    category_id=None,
    receipt_path=None,
    ocr_text=None,
    gst_amount=None,
    pst_amount=None,
    hst_amount=None,
    line_items=None
):
    supabase = init_connection()
    try:
        supabase.table("expenses").insert({
            "report_id":   report_id,
            "expense_date": str(expense_date),
            "vendor":       vendor,
            "description":  description,
            "amount":       amount,
            "currency":     currency,
            "category_id":  category_id,
            "receipt_path": receipt_path,
            "ocr_text":     ocr_text,
            "gst_amount":   gst_amount,
            "pst_amount":   pst_amount,
            "hst_amount":   hst_amount,
            "line_items":   json.dumps(line_items) if line_items else None
        }).execute()
        return True
    except Exception as e:
        st.error(f"Error saving expense item: {e}")
        return False

def update_expense_item(expense_id, updates: dict):
    supabase = init_connection()
    try:
        supabase.table("expenses").update(updates).eq("id", expense_id).execute()
        return True
    except Exception as e:
        st.error(f"Error updating expense item: {e}")
        return False

def get_reports_for_user(user_id: str):
    """Fetch all reports submitted by a given user, newest first."""
    supabase = init_connection()
    resp = (
        supabase
        .table("reports")
        .select("*, user:users!left(name)")
        .eq("user_id", user_id)
        .order("submission_date", desc=True)
        .execute()
    )
    return pd.DataFrame(resp.data)

def get_expenses_for_report(report_id: str):
    supabase = init_connection()
    try:
        resp = supabase.table("expenses").select(
            "*, category:categories!left(id, name, gl_account)"
        ).eq("report_id", report_id).execute()
        expenses = resp.data
        for exp in expenses:
            cat = exp.pop("category", None)
            if isinstance(cat, dict):
                exp["category_name"] = cat.get("name")
                exp["gl_account"]    = cat.get("gl_account")
            else:
                exp["category_name"] = None
                exp["gl_account"]    = None
        return pd.DataFrame(expenses)
    except Exception as e:
        st.error(f"Error fetching expense items: {e}")
        return pd.DataFrame()

def get_receipt_public_url(path: str):
    supabase = init_connection()
    if not path:
        return ""
    return supabase.storage.from_("receipts").get_public_url(path)

def get_reports_for_approver(approver_id: str):
    supabase = init_connection()
    try:
        apr = supabase.table("users").select("default_category_id")\
            .eq("id", approver_id).maybe_single().execute()
        cat_id = apr.data.get("default_category_id") if apr.data else None
        if not cat_id:
            return pd.DataFrame()
        emps = supabase.table("users").select("id")\
            .eq("default_category_id", cat_id)\
            .neq("id", approver_id).execute()
        emp_ids = [u["id"] for u in emps.data]
        if not emp_ids:
            return pd.DataFrame()
        rep = supabase.table("reports")\
            .select("*, user:users!left(name)")\
            .in_("user_id", emp_ids)\
            .order("submission_date", desc=True)\
            .execute()
        return pd.DataFrame(rep.data)
    except Exception as e:
        st.error(f"Error fetching reports for approver: {e}")
        return pd.DataFrame()

def get_all_reports():
    supabase = init_connection()
    try:
        resp = supabase.table("reports").select(
            "*, user:users!left(name)"
        ).order("submission_date", desc=True).execute()
        return pd.DataFrame(resp.data)
    except Exception as e:
        st.error(f"Error fetching all reports: {e}")
        return pd.DataFrame()

def update_report_status(report_id, status, comment=None):
    supabase = init_connection()
    try:
        updates = {"status": status}
        if comment:
            updates["approver_comment"] = comment
        supabase.table("reports").update(updates).eq("id", report_id).execute()
        return True
    except Exception as e:
        st.error(f"Error updating report status: {e}")
        return False

def get_all_categories():
    supabase = init_connection()
    try:
        resp = supabase.table("categories").select("id, name, gl_account")\
            .order("name", desc=False).execute()
        return resp.data
    except Exception as e:
        st.error(f"Error fetching categories: {e}")
        return []

def add_category(name, gl_account):
    supabase = init_connection()
    try:
        if supabase.table("categories").select("id", count="exact")\
            .eq("name", name).execute().count > 0:
            st.warning(f"Category '{name}' already exists.")
            return False
        supabase.table("categories").insert({
            "name":       name,
            "gl_account": gl_account
        }).execute()
        return True
    except Exception as e:
        st.error(f"Error adding category: {e}")
        return False

def update_category(category_id, name, gl_account):
    supabase = init_connection()
    try:
        supabase.table("categories").update({
            "name":       name,
            "gl_account": gl_account
        }).eq("id", category_id).execute()
        return True
    except Exception as e:
        st.error(f"Error updating category: {e}")
        return False

def delete_category(category_id):
    supabase = init_connection()
    try:
        supabase.table("categories").delete().eq("id", category_id).execute()
        return True
    except Exception as e:
        st.error(f"Error deleting category: {e}")
        return False

# (any XML‐generation helper functions follow…)
