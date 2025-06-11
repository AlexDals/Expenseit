import streamlit as st
from supabase import create_client, Client
import pandas as pd
from datetime import datetime
import os
import json

@st.cache_resource
def init_connection() -> Client:
    # ... (no changes to this function)
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key)
    except KeyError:
        st.error("Supabase credentials not found. Please add your secrets in the Streamlit Cloud dashboard.")
        st.stop()

def fetch_all_users_for_auth() -> dict:
    supabase = init_connection()
    try:
        # Now also fetching the role for session state
        response = supabase.table('users').select("username, email, name, hashed_password, role").execute()
        users_data = response.data
        credentials = {"usernames": {}}
        for user in users_data:
            credentials["usernames"][user["username"]] = {
                "email": user["email"],
                "name": user["name"],
                "password": user["hashed_password"],
                "role": user["role"] # Store role
            }
        return credentials
    except Exception as e:
        st.error(f"Error fetching users: {e}")
        return {"usernames": {}}

# --- NEW USER MANAGEMENT FUNCTIONS ---

def get_all_users():
    """Fetches all user data for the management page."""
    supabase = init_connection()
    try:
        response = supabase.table('users').select("id, username, name, email, role, approver_id").execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"Error fetching all users: {e}")
        return pd.DataFrame()

def get_all_approvers():
    """Fetches all users with the 'approver' role."""
    supabase = init_connection()
    try:
        response = supabase.table('users').select("id, name").eq('role', 'approver').execute()
        return response.data
    except Exception as e:
        st.error(f"Error fetching approvers: {e}")
        return []

def update_user_details(user_id, role, approver_id):
    """Updates a user's role and/or assigned approver."""
    supabase = init_connection()
    try:
        supabase.table('users').update({
            "role": role,
            "approver_id": approver_id
        }).eq('id', user_id).execute()
        return True
    except Exception as e:
        st.error(f"Error updating user details: {e}")
        return False

# --- NEW REPORT FETCHING FUNCTIONS ---

def get_reports_for_approver(approver_id):
    """Fetches all reports submitted by users assigned to this approver."""
    supabase = init_connection()
    try:
        # Find all employees assigned to this approver
        employees_response = supabase.table('users').select('id').eq('approver_id', approver_id).execute()
        employee_ids = [user['id'] for user in employees_response.data]
        
        if not employee_ids:
            return pd.DataFrame()

        # Fetch reports for those employees
        reports_response = supabase.table('reports').select("*").in_('user_id', employee_ids).order('submission_date', desc=True).execute()
        return pd.DataFrame(reports_response.data)
    except Exception as e:
        st.error(f"Error fetching reports for approver: {e}")
        return pd.DataFrame()

def get_all_reports():
    """Fetches all reports for admin view."""
    supabase = init_connection()
    try:
        response = supabase.table('reports').select("*").order('submission_date', desc=True).execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"Error fetching all reports: {e}")
        return pd.DataFrame()

def update_report_status(report_id, status):
    """Updates the status of a specific report."""
    supabase = init_connection()
    try:
        supabase.table('reports').update({"status": status}).eq('id', report_id).execute()
        return True
    except Exception as e:
        st.error(f"Error updating report status: {e}")
        return False
        
# --- EXISTING FUNCTIONS (No changes needed) ---
# register_user, get_user_id_by_username, upload_receipt, 
# add_report, add_expense_item, get_reports_for_user, 
# get_expenses_for_report, get_receipt_public_url
# All of these functions remain the same as the last version you had.
# ... (rest of the functions from the last version) ...
