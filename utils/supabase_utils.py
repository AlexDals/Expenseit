import streamlit as st
from supabase import create_client, Client
import pandas as pd
from datetime import datetime
import os

# The init_connection function is perfect as is, decorated with cache_resource.
@st.cache_resource
def init_connection() -> Client:
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key)
    except KeyError:
        st.error("Supabase credentials not found in secrets.toml. Please add them.")
        st.stop()

# --- CHANGE 1: REMOVE THE AUTOMATIC CONNECTION ---
# The line "supabase = init_connection()" that was here has been removed.
# We will now call init_connection() inside each function instead.

def fetch_all_users_for_auth() -> dict:
    supabase = init_connection() # Connect when the function is called
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

def register_user(username, name, email, hashed_password) -> bool:
    supabase = init_connection() # Connect when the function is called
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

def get_user_id_by_username(username: str) -> str | None:
    supabase = init_connection() # Connect when the function is called
    try:
        response = supabase.table('users').select('id').eq('username', username).execute()
        return response.data[0]['id'] if response.data else None
    except Exception as e:
        st.error(f"Error fetching user ID: {e}")
        return None

def upload_receipt(uploaded_file, username: str) -> str | None:
    supabase = init_connection() # Connect when the function is called
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

def add_report(user_id, report_name, total_amount) -> str | None:
    supabase = init_connection() # Connect when the function is called
    try:
        response = supabase.table('reports').insert({
            "user_id": user_id, "report_name": report_name, "submission_date": datetime.now().isoformat(), "total_amount": total_amount
        }).execute()
        return response.data[0]['id'] if response.data else None
    except Exception as e:
        st.error(f"Error adding report: {e}")
        return None

# In utils/supabase_utils.py, replace the add_expense_item function with this one.

# In utils/supabase_utils.py, replace the add_expense_item function.
# The other functions can remain the same.

# In utils/supabase_utils.py, replace the add_expense_item function
import json # Make sure to import json at the top of the file

def add_expense_item(report_id, expense_date, vendor, description, amount, receipt_path=None, ocr_text=None, gst_amount=None, pst_amount=None, hst_amount=None, line_items=None):
    """Adds a new expense item, including structured line items."""
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
            "line_items": json.dumps(line_items) if line_items else None # Store as JSON string
        }).execute()
        return True
    except Exception as e:
        st.error(f"Error saving item '{description}': {e}")
        return False

def get_reports_for_user(user_id):
    supabase = init_connection() # Connect when the function is called
    response = supabase.table('reports').select("*").eq('user_id', user_id).order('submission_date', desc=True).execute()
    return pd.DataFrame(response.data)

def get_expenses_for_report(report_id):
    supabase = init_connection() # Connect when the function is called
    response = supabase.table('expenses').select("*").eq('report_id', report_id).execute()
    return pd.DataFrame(response.data)

def get_receipt_public_url(path: str) -> str:
    supabase = init_connection() # Connect when the function is called
    if not path: return ""
    return supabase.storage.from_('receipts').get_public_url(path)
