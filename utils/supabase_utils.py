import streamlit as st
from supabase import create_client, Client
import pandas as pd
import json
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
        resp = supabase.table("users").select("id, role").eq("username", username).maybe_single().execute()
        return resp.data or {}
    except Exception:
        logger.exception("Error fetching user by username")
        return {}


def get_single_user_details(user_id: str) -> dict:
    """
    Fetches full details for a single user.
    """
    supabase = init_connection()
    try:
        resp = supabase.table("users").select(
            "id, username, name, email, role, approver_id, default_category_id"
        ).eq("id", user_id).maybe_single().execute()
        return resp.data or {}
    except Exception:
        logger.exception("Error fetching user details")
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
            "role": role
        }).execute()
        return True
    except Exception:
        logger.exception("Error registering user")
        return False


def update_user_details(user_id: str, role: str, approver_id: int = None, default_category_id: int = None) -> bool:
    """
    Update user role, approver, default_category.
    """
    supabase = init_connection()
    try:
        updates = {"role": role}
        if approver_id is not None:
            updates["approver_id"] = approver_id
        if default_category_id is not None:
            updates["default_category_id"] = default_category_id
        supabase.table("users").update(updates).eq("id", user_id).execute()
        return True
    except Exception:
        logger.exception("Error updating user details")
        return False


def delete_user(user_id: str) -> bool:
    """
    Delete a user from database.
    """
    supabase = init_connection()
    try:
        supabase.table("users").delete().eq("id", user_id).execute()
        return True
    except Exception:
        logger.exception("Error deleting user")
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
        resp = supabase.table("categories").select("id, name, gl_account").execute()
        return pd.DataFrame(resp.data or [])
    except Exception:
        logger.exception("Error fetching categories")
        return pd.DataFrame()


def add_category(name: str, gl_account: str = "") -> bool:
    """
    Add a new category.
    """
    supabase = init_connection()
    try:
        supabase.table("categories").insert({"name": name, "gl_account": gl_account}).execute()
        return True
    except Exception:
        logger.exception("Error adding category")
        return False


def update_category(category_id: str, name: str, gl_account: str = "") -> bool:
    """
    Update category.
    """
    supabase = init_connection()
    try:
        supabase.table("categories").update({"name": name, "gl_account": gl_account}).eq("id", category_id).execute()
        return True
    except Exception:
        logger.exception("Error updating category")
        return False


def delete_category(category_id: str) -> bool:
    """
    Delete a category.
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
    Update department.
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
    Delete a department.
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
            "report_name": report_name,
            "submission_date": submission_date
        }).execute()
        return resp.data[0]["id"] if resp.data else ""
    except Exception:
        logger.exception("Error creating report")
        return ""


def fetch_reports(username: str = None) -> pd.DataFrame:
    """
    Fetch all reports or filter by username.
    """
    supabase = init_connection()
    try:
        query = supabase.table("reports").select("*")
        if username:
            query = query.eq("username", username)
        resp = query.execute()
        return pd.DataFrame(resp.data or [])
    except Exception:
        logger.exception("Error fetching reports")
        return pd.DataFrame()


def delete_report(report_id: str) -> bool:
    """
    Delete a report and its associated expense items.
    """
    supabase = init_connection()
    try:
        supabase.table("expense_items").delete().eq("report_id", report_id).execute()
        supabase.table("reports").delete().eq("id", report_id).execute()
        return True
    except Exception:
        logger.exception("Error deleting report")
        return False


def add_expense_item(report_id: str, description: str, amount: float, date: datetime, receipt_url: str = None, category_id: int = None, gst_amount: float = 0.0, pst_amount: float = 0.0, hst_amount: float = 0.0, line_items: list = None) -> bool:
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
            "category_id": category_id,
            "gst_amount": gst_amount,
            "pst_amount": pst_amount,
            "hst_amount": hst_amount,
            "line_items": json.dumps(line_items) if line_items else None
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
        resp = supabase.table("expense_items").select("*").eq("report_id", report_id).execute()
        items = resp.data or []
        for item in items:
            if item.get("line_items") and isinstance(item["line_items"], str):
                try:
                    item["line_items"] = json.loads(item["line_items"])
                except json.JSONDecodeError:
                    item["line_items"] = []
        return pd.DataFrame(items)
    except Exception:
        logger.exception("Error fetching expense items")
        return pd.DataFrame()


def update_expense_item(item_id: str, **kwargs) -> bool:
    """
    Update given fields on an expense item.
    """
    supabase = init_connection()
    try:
        if "line_items" in kwargs:
            kwargs["line_items"] = json.dumps(kwargs["line_items"])
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

def upload_receipt(uploaded_file, username: str) -> str:
    """
    Upload a receipt file (Streamlit UploadedFile) and return its public URL.
    """
    supabase = init_connection()
    try:
        content = uploaded_file.getvalue()
        filename = os.path.basename(uploaded_file.name)
        storage_path = f"receipts/{username}/{uuid.uuid4()}_{filename}"
        supabase.storage.from_("receipts").upload(storage_path, content)
        url_data = supabase.storage.from_("receipts").get_public_url(storage_path)
        return url_data.get("publicUrl", "") if isinstance(url_data, dict) else url_data.public_url
    except Exception:
        logger.exception("Error uploading receipt")
        return ""
