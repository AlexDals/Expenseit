import streamlit as st
from supabase import create_client, Client
import pandas as pd
from datetime import datetime
import os
import json

@st.cache_resource
def init_connection():
    """Initializes and returns a Supabase client."""
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key)
    except KeyError:
        st.error("Supabase credentials not found. Please add your secrets in the Streamlit Cloud dashboard.")
        st.stop()

# --- THIS FUNCTION IS NOW SIMPLER ---
def fetch_all_users_for_auth():
    """Fetches all users from the database for the authenticator."""
    supabase = init_connection()
    try:
        # No longer needs to select the 'role' column
        response = supabase.table('users').select("username, email, name, hashed_password").execute()
        users_data = response.data
        credentials = {"usernames": {}}
        for user in users_data:
            credentials["usernames"][user["username"]] = {
                "email": user["email"],
                "name": user["name"],
                "password": user["hashed_password"]
            }
        return credentials
    except Exception as e:
        st.error(f"Error fetching users: {e}")
        return {"usernames": {}}

# --- NEW FUNCTION TO GET A SINGLE USER'S ROLE ---
def get_user_role(username: str):
    """Fetches just the role for a specific username."""
    supabase = init_connection()
    try:
        response = supabase.table('users').select('role').eq('username', username).execute()
        if response.data:
            return response.data[0].get('role')
        return None
    except Exception as e:
        st.error(f"Error fetching user role: {e}")
        return None

# --- ALL OTHER FUNCTIONS REMAIN THE SAME ---
def register_user(username, name, email, hashed_password) -> bool:
    # ... (no changes to this function)
def get_user_id_by_username(username: str):
    # ... (no changes to this function)
def upload_receipt(uploaded_file, username: str):
    # ... (no changes to this function)
def add_report(user_id, report_name, total_amount):
    # ... (no changes to this function)
def add_expense_item(report_id, expense_date, vendor, description, amount, receipt_path=None, ocr_text=None, gst_amount=None, pst_amount=None, hst_amount=None, line_items=None):
    # ... (no changes to this function)
def get_reports_for_user(user_id):
    # ... (no changes to this function)
def get_expenses_for_report(report_id):
    # ... (no changes to this function)
def get_receipt_public_url(path: str):
    # ... (no changes to this function)
def get_all_users():
    # ... (no changes to this function)
def get_all_approvers():
    # ... (no changes to this function)
def update_user_details(user_id, role, approver_id):
    # ... (no changes to this function)
def get_reports_for_approver(approver_id):
    # ... (no changes to this function)
def get_all_reports():
    # ... (no changes to this function)
def update_report_status(report_id, status):
    # ... (no changes to this function)
