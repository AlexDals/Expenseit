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
        st.error("Supabase credentials not found. Please add your secrets in the Streamlit Cloud dashboard.")
        st.stop()

def fetch_all_users_for_auth():
    supabase = init_connection()
    try:
        response = supabase.table('users').select("id, username, email, name, hashed_password, role").execute()
        users_data = response.data
        credentials = {"usernames": {}}
        for user in users_data:
            credentials["usernames"][user["username"]] = {
                "id": user["id"], "email": user["email"], "name": user["name"], 
                "password": user["hashed_password"], "role": user["role"]
            }
        return credentials
    except Exception as e:
        st.error(f"Error fetching users: {e}"); return {"usernames": {}}

def register_user(username, name, email, hashed_password, role='user'):
    supabase = init_connection()
    try:
        if supabase.table('users').select('id', count='exact').eq('username', username).execute().count > 0:
            st.error("Username already taken."); return False
        supabase.table('users').insert({"username": username, "name": name, "email": email, "hashed_password": hashed_password, "role": role}).execute()
        return True
    except Exception as e:
        st.error(f"Error during registration: {e}"); return False

def get_user_role(username: str):
    supabase = init_connection()
    try:
        response = supabase.table('users').select('role').eq('username', username).execute()
        return response.data[0].get('role') if response.data else None
    except Exception as e:
        st.error(f"Error fetching user role: {e}"); return None

def get_user_id_by_username(username: str):
    supabase = init_connection()
    try:
        response = supabase.table('users').select('id').eq('username', username).execute()
        return response.data[0]['id'] if response.data else None
    except Exception as e:
        st.error(f"Error fetching user ID: {e}"); return None

def get_all_users():
    supabase = init_connection()
    try:
        response = supabase.table('users').select("id, username, name, email, role, approver_id, department").execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"Error fetching all users: {e}"); return pd.DataFrame()

# --- THIS FUNCTION IS MODIFIED ---
def get_all_approvers():
    """Fetches all users with the 'approver' OR 'admin' role."""
    supabase = init_connection()
    try:
        # FIX: Use .in_() to select users where the role is one of the specified values.
        response = supabase.table('users').select("id, name").in_('role', ['approver', 'admin']).execute()
        return response.data
    except Exception as e:
        st.error(f"Error fetching approvers: {e}"); return []

def update_user_details(user_id, role, approver_id, department):
    supabase = init_connection()
    try:
        supabase.table('users').update({"role": role, "approver_id": approver_id, "department": department}).eq('id', user_id).execute()
        return True
    except Exception as e:
        st.error(f"Error updating user details: {e}"); return False

def add_report(user_id, report_name, total_amount):
    supabase = init_connection()
    try:
        response = supabase.table('reports').insert({"user_id": user_id, "report_name": report_name, "submission_date": datetime.now().isoformat(), "total_amount": total_amount, "status": "Submitted"}).execute()
        return response.data[0]['id'] if response.data else None
    except Exception as e:
        st.error(f"Error adding report: {e}"); return None

def add_expense_item(report_id, expense_date, vendor, description, amount, currency='CAD', category_id=None, receipt_path=None, ocr_text=None, gst_amount=None, pst_amount=None, hst_amount=None, line_items=None):
    supabase = init_connection()
    try:
        supabase.table('expenses').insert({
            "report_id": report_id, "expense_date": str(expense_date), "vendor": vendor,
            "description": description, "amount": amount, "category_id": category_id,
            "receipt_path": receipt_path, "ocr_text": ocr_text, "gst_amount": gst_amount,
            "pst_amount": pst_amount, "hst_amount": hst_amount,
            "line_items": json.dumps(line_items) if line_items else None, "currency": currency
        }).execute()
        return True
    except Exception as e:
        st.error(f"Error saving an expense item: {e}"); return False

def update_expense_item(expense_id, updates: dict):
    supabase = init_connection()
    try:
        supabase.table('expenses').update(updates).eq('id', expense_id).execute()
        return True
    except Exception as e:
        st.error(f"Error updating expense item: {e}"); return False

def get_reports_for_user(user_id):
    supabase = init_connection()
    response = supabase.table('reports').select("*, user:users!left(name)").eq('user_id', user_id).order('submission_date', desc=True).execute()
    return pd.DataFrame(response.data)

def get_expenses_for_report(report_id):
    supabase = init_connection()
    try:
        response = supabase.table('expenses').select("*, category:categories!left(name)").eq('report_id', report_id).execute()
        expenses = response.data
        for expense in expenses:
            if expense.get('category') and isinstance(expense['category'], dict):
                expense['category_name'] = expense['category'].get('name')
            else:
                expense['category_name'] = None
            expense.pop('category', None)
        return pd.DataFrame(expenses)
    except Exception as e:
        st.error(f"Error fetching expense items: {e}"); return pd.DataFrame()

def get_receipt_public_url(path: str):
    supabase = init_connection()
    if not path: return ""
    return supabase.storage.from_('receipts').get_public_url(path)

def get_reports_for_approver(approver_id):
    supabase = init_connection()
    try:
        approver_dept_response = supabase.table('users').select('department').eq('id', approver_id).maybe_single().execute()
        if not approver_dept_response.data or not approver_dept_response.data.get('department'):
            return pd.DataFrame()
        approver_department = approver_dept_response.data['department']
        employees_response = supabase.table('users').select('id').eq('department', approver_department).neq('id', approver_id).execute()
        employee_ids = [user['id'] for user in employees_response.data]
        if not employee_ids: return pd.DataFrame()
        reports_response = supabase.table('reports').select("*, user:users!left(name)").in_('user_id', employee_ids).order('submission_date', desc=True).execute()
        return pd.DataFrame(reports_response.data)
    except Exception as e:
        st.error(f"Error fetching reports for approver: {e}"); return pd.DataFrame()

def get_all_reports():
    supabase = init_connection()
    try:
        response = supabase.table('reports').select("*, user:users!left(name)").order('submission_date', desc=True).execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"Error fetching all reports: {e}"); return pd.DataFrame()

def update_report_status(report_id, status, comment=None):
    supabase = init_connection()
    try:
        updates = {"status": status}
        if comment: updates["approver_comment"] = comment
        supabase.table('reports').update(updates).eq('id', report_id).execute()
        return True
    except Exception as e:
        st.error(f"Error updating report status: {e}"); return False

def get_all_categories():
    supabase = init_connection()
    try:
        response = supabase.table('categories').select("id, name, gl_account").order('name', desc=False).execute()
        return response.data
    except Exception as e:
        st.error(f"Error fetching categories: {e}"); return []

def add_category(name, gl_account):
    supabase = init_connection()
    try:
        if supabase.table('categories').select('id', count='exact').eq('name', name).execute().count > 0:
            st.warning(f"Category '{name}' already exists."); return False
        supabase.table('categories').insert({"name": name, "gl_account": gl_account}).execute()
        return True
    except Exception as e:
        st.error(f"Error adding category: {e}"); return False

def update_category(category_id, name, gl_account):
    supabase = init_connection()
    try:
        supabase.table('categories').update({"name": name, "gl_account": gl_account}).eq('id', category_id).execute()
        return True
    except Exception as e:
        st.error(f"Error updating category: {e}"); return False

def delete_category(category_id):
    supabase = init_connection()
    try:
        supabase.table('categories').delete().eq('id', category_id).execute()
        return True
    except Exception as e:
        st.error(f"Error deleting category: {e}"); return False
        
def generate_report_xml(report_data: pd.Series, expenses_data: pd.DataFrame, submitter_name: str):
    # ... (XML generation function remains the same) ...
