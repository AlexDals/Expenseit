import streamlit as st
from supabase import create_client, Client
import pandas as pd
from datetime import datetime
import os
import uuid
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@st.cache_resource
def init_connection() -> Client:
    """
    Initialize and cache the Supabase client using credentials stored in streamlit secrets.
    """
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key)
    except KeyError:
        st.error("Supabase credentials not found.")
        st.stop()


# ---------------------------------------------
# User Authentication & Management
# ---------------------------------------------

def fetch_all_users_for_auth() -> dict:
    """
    Fetch all users to configure streamlit_authenticator credentials.
    Returns: {"usernames": {username: {id, email, name, password, role}}}
    """
    supabase = init_connection()
    try:
        resp = supabase.table("users").select(
            "id, username, email, name, hashed_password, role"
        ).execute()
        users = resp.data or []
        creds = {"usernames": {}}
        for u in users:
            creds["usernames"][u["username"]] = {
                "id": u["id"],
                "email": u["email"],
                "name": u["name"],
                "password": u["hashed_password"],
                "role": u["role"],
            }
        return creds
    except Exception:
        logger.exception("Error fetching users for auth")
        return {"usernames": {}}


def get_user_by_username(username: str) -> dict:
    """
    Returns a user's {id, role} or empty dict.
    """
    supabase = init_connection()
    try:
        resp = (supabase.table("users")
                .select("id, role")
                .eq("username", username)
                .maybe_single()
                .execute())
        return resp.data or {}
    except Exception:
        logger.exception("Error fetching user by username")
        return {}


def register_user(username: str, name: str, email: str, hashed_password: str, role: str = "user") -> bool:
    """
    Register a new user. Returns True on success.
    """
    supabase = init_connection()
    try:
        if not all([username, name, email, hashed_password, role]):
            st.error("All fields required.")
            return False
        exists = supabase.table("users").select("id", count="exact").eq("username", username).execute()
        if exists.count > 0:
            st.error(f"Username '{username}' taken.")
            return False
        supabase.table("users").insert({
            "username": username,
            "name": name,
            "email": email,
            "hashed_password": hashed_password,
            "role": role,
        }).execute()
        return True
    except Exception:
        logger.exception("Error registering user")
        return False


# ---------------------------------------------
# Category Management
# ---------------------------------------------

def fetch_categories() -> pd.DataFrame:
    """
    Retrieve all categories into a DataFrame.
    """
    supabase = init_connection()
    try:
        resp = supabase.table("categories").select("id, name").execute()
        return pd.DataFrame(resp.data or [])
    except Exception:
        logger.exception("Error fetching categories")
        return pd.DataFrame()


def add_category(name: str) -> bool:
    """
    Add a new category.
    """
    supabase = init_connection()
    try:
        supabase.table("categories").insert({"name": name}).execute()
        return True
    except Exception:
        logger.exception("Error adding category")
        return False


def update_category(category_id: str, name: str) -> bool:
    """
    Update category name.
    """
    supabase = init_connection()
    try:
        supabase.table("categories").update({"name": name}).eq("id", category_id).execute()
        return True
    except Exception:
        logger.exception("Error updating category")
        return False


def delete_category(category_id: str) -> bool:
    """
    Delete a category by ID.
    """
    supabase = init_connection()
    try:
        supabase.table("categories").delete().eq("id", category_id).execute()
        return True
    except Exception:
        logger.exception("Error deleting category")
        return False


# ---------------------------------------------
# Department Management
# ---------------------------------------------

def fetch_departments() -> pd.DataFrame:
    """
    Retrieve all departments into a DataFrame.
    """
    supabase = init_connection()
    try:
        resp = supabase.table("departments").select("id, name").execute()
        return pd.DataFrame(resp.data or [])
    except Exception:
        logger.exception("Error fetching departments")
        return pd.DataFrame()


def add_department(name: str) -> bool:
    """
    Add a new department.
    """
    supabase = init_connection()
    try:
        supabase.table("departments").insert({"name": name}).execute()
        return True
    except Exception:
        logger.exception("Error adding department")
        return False


def update_department(department_id: str, name: str) -> bool:
    """
    Update department name.
    """
    supabase = init_connection()
    try:
        supabase.table("departments").update({"name": name}).eq("id", department_id).execute()
        return True
    except Exception:
        logger.exception("Error updating department")
        return False


def delete_department(department_id: str) -> bool:
    """
    Delete a department by ID.
    """
    supabase = init_connection()
    try:
        supabase.table("departments").delete().eq("id", department_id).execute()
        return True
    except Exception:
        logger.exception("Error deleting department")
        return False


# ---------------------------------------------
# Report & Expense Management
# ---------------------------------------------

def create_report(username: str, report_name: str, submission_date: datetime = None) -> str:
    """
    Create a new report and return its ID.
    """
    supabase = init_connection()
    try:
        submission_date = submission_date or datetime.utcnow()
        resp = supabase.table("reports").insert({
            "username": username,
            "name": report_name,
            "submitted_at": submission_date,
        }).execute()
        return resp.data[0]["id"]  # type: ignore
    except Exception:
        logger.exception("Error creating report")
        return ""


def fetch_reports(username: str = None) -> pd.DataFrame:
    """
    Fetch all reports or filter by username.
    """
    supabase = init_connection()
    try:
        query = supabase.table("reports").select("id, username, name, submitted_at")
        if username:
            query = query.eq("username", username)
        resp = query.execute()
        return pd.DataFrame(resp.data or [])
    except Exception:
        logger.exception("Error fetching reports")
        return pd.DataFrame()


def delete_report(report_id: str) -> bool:
    """
    Delete a report and its line items.
    """
    supabase = init_connection()
    try:
        supabase.table("expense_items").delete().eq("report_id", report_id).execute()
        supabase.table("reports").delete().eq("id", report_id).execute()
        return True
    except Exception:
        logger.exception("Error deleting report")
        return False


def add_expense_item(report_id: str, description: str, amount: float, date: datetime, receipt_url: str = None) -> bool:
    """
    Add a line item to a report.
    """
    supabase = init_connection()
    try:
        supabase.table("expense_items").insert({
            "report_id": report_id,
            "description": description,
            "amount": amount,
            "date": date,
            "receipt_url": receipt_url,
        }).execute()
        return True
    except Exception:
        logger.exception("Error adding expense item")
        return False


def fetch_expense_items(report_id: str) -> pd.DataFrame:
    """
    Fetch all line items for a report.
    """
    supabase = init_connection()
    try:
        resp = supabase.table("expense_items").select("id, description, amount, date, receipt_url").eq("report_id", report_id).execute()
        return pd.DataFrame(resp.data or [])
    except Exception:
        logger.exception("Error fetching expense items")
        return pd.DataFrame()


def update_expense_item(item_id: str, **kwargs) -> bool:
    """
    Update given fields on an expense item.
    """
    supabase = init_connection()
    try:
        supabase.table("expense_items").update(kwargs).eq("id", item_id).execute()
        return True
    except Exception:
        logger.exception("Error updating expense item")
        return False


def delete_expense_item(item_id: str) -> bool:
    """
    Delete a single expense item.
    """
    supabase = init_connection()
    try:
        supabase.table("expense_items").delete().eq("id", item_id).execute()
        return True
    except Exception:
        logger.exception("Error deleting expense item")
        return False


# ---------------------------------------------
# Receipt Upload
# ---------------------------------------------

def upload_receipt(file_path: str, username: str) -> str:
    """
    Upload a receipt file and return its public URL.
    """
    supabase = init_connection()
    try:
        filename = os.path.basename(file_path)
        storage_path = f"receipts/{username}/{uuid.uuid4()}_{filename}"
        supabase.storage.from_("receipts").upload(storage_path, file_path)
        return supabase.storage.from_("receipts").get_public_url(storage_path).public_url
    except Exception:
        logger.exception("Error uploading receipt")
        return ""
