import streamlit as st
from supabase import create_client, Client
import pandas as pd
from datetime import datetime

@st.cache_resource
def init_connection() -> Client:
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key)
    except KeyError:
        st.error("Supabase credentials not found in secrets. Please add them.")
        st.stop()

supabase = init_connection()

def fetch_all_users_for_auth() -> dict:
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
    try:
        response = supabase.table('users').select('id').eq('username', username).execute()
        return response.data[0]['id'] if response.data else None
    except Exception as e:
        st.error(f"Error fetching user ID: {e}")
        return None

def upload_receipt(image_bytes, username: str) -> str | None:
    try:
        file_path = f"{username}/{datetime.now().timestamp()}_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
        response = supabase.storage.from_("receipts").upload(file=image_bytes, path=file_path, file_options={"content-type": "image/png"})
        
        if response.status_code == 200:
            return file_path
        return None
    except Exception as e:
        st.error(f"Error uploading receipt: {e}")
        return None

def add_report(user_id, report_name, total_amount) -> str | None:
    try:
        response = supabase.table('reports').insert({
            "user_id": user_id, "report_name": report_name, "submission_date": datetime.now().isoformat(), "total_amount": total_amount
        }).execute()
        return response.data[0]['id'] if response.data else None
    except Exception as e:
        st.error(f"Error adding report: {e}")
        return None

def add_expense_item(report_id, expense_date, vendor, description, amount, receipt_path=None, ocr_text=None):
    try:
        supabase.table('expenses').insert({
            "report_id": report_id, "expense_date": str(expense_date), "vendor": vendor,
            "description": description, "amount": amount, "receipt_path": receipt_path, "ocr_text": ocr_text
        }).execute()
    except Exception as e:
        st.error(f"Error adding expense item: {e}")

def get_reports_for_user(user_id):
    response = supabase.table('reports').select("*").eq('user_id', user_id).order('submission_date', desc=True).execute()
    return pd.DataFrame(response.data)

def get_expenses_for_report(report_id):
    response = supabase.table('expenses').select("*").eq('report_id', report_id).execute()
    return pd.DataFrame(response.data)

def get_receipt_public_url(path: str) -> str:
    if not path: return ""
    return supabase.storage.from_('receipts').get_public_url(path)
