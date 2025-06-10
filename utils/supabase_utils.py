import streamlit as st
from supabase import create_client, Client
import pandas as pd
from datetime import datetime
import os
import json

@st.cache_resource
def init_connection():
    """Initializes and returns a Supabase client, cached for performance."""
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key)
    except KeyError:
        st.error("Supabase credentials not found. Please add your secrets in the Streamlit Cloud dashboard.")
        st.stop()

def fetch_all_users_for_auth():
    """Fetches all users from the database for the authenticator."""
    supabase = init_connection()
    try:
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

def register_user(username, name, email, hashed_password):
    """Registers a new user in the database."""
    supabase = init_connection()
    try:
        user_exists = supabase.table('users').select('username').eq('username', username).execute().data
        if user_exists:
            st.error("Username already taken. Please choose another one.")
            return False
        response = supabase.table('users').insert({
            "username": username, "name": name, "email": email, "hashed_password": hashed_password
        }).execute()
        return len(response.data) > 0
    except Exception as e:
        st.error(f"Error during registration: {e}")
        return False

def get_user_id_by_username(username):
    """Fetches the UUID for a given username."""
    supabase = init_connection()
    try:
        response = supabase.table('users').select('id').eq('username', username).execute()
        return response.data[0]['id'] if response.data else None
    except Exception as e:
        st.error(f"Error fetching user ID: {e}")
        return None

def upload_receipt(uploaded_file, username):
    """Uploads a receipt file to Supabase Storage."""
    supabase = init_connection()
    try:
        file_bytes = uploaded_file.getvalue()
        file_ext = os.path.splitext(uploaded_file.name)[1]
        file_path = f"{username}/{datetime.now().timestamp()}_{datetime.now().strftime('%Y%m%d%H%M%S')}{file_ext}"
        supabase.storage.from_("receipts").upload(
            file=file_bytes,
            path=file_path,
            file_options={"content-type": uploaded_file.type}
        )
        return file_path
    except Exception as e:
        st.error(f"Error uploading receipt: {e}")
        return None

def add_report(user_id, report_name, total_amount):
    """Adds a new report header to the database."""
    supabase = init_connection()
    try:
        response = supabase.table('reports').insert({
            "user_id": user_id,
            "report_name": report_name,
            "submission_date": datetime.now().isoformat(),
            "total_amount": total_amount
        }).execute()
        return response.data[0]['id'] if response.data else None
    except Exception as e:
        st.error(f"Error adding report: {e}")
        return None

def add_expense_item(report_id, expense_date, vendor, description, amount, receipt_path=None, ocr_text=None, gst_amount=None, pst_amount=None, hst_amount=None, line_items=None):
    """Adds a new expense item to a report, including all details."""
    supabase = init_connection()
    try:
        supabase.table('expenses').insert({
            "report_id": report_id,
            "expense_date": str(expense_date),
            "vendor": vendor,
            "description": description,
            "amount": amount,
            "receipt_path": receipt_path,
            "ocr_text": ocr_text,
            "gst_amount": gst_amount,
            "pst_amount": pst_amount,
            "hst_amount": hst_amount,
            "line_items": json.dumps(line_items) if line_items else None
        }).execute()
        return True
    except Exception as e:
        st.error(f"Error saving an expense item: {e}")
        return False

def get_reports_for_user(user_id):
    """Fetches all report summaries for a specific user."""
    supabase = init_connection()
    response = supabase.table('reports').select("*").eq('user_id', user_id).order('submission_date', desc=True).execute()
    return pd.DataFrame(response.data)

def get_expenses_for_report(report_id):
    """Fetches all expense items for a specific report."""
    supabase = init_connection()
    response = supabase.table('expenses').select("*").
