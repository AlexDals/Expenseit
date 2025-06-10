import streamlit as st
from supabase import create_client, Client
import pandas as pd
from datetime import datetime
import os
import json

@st.cache_resource
def init_connection() -> Client:
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key)
    except KeyError:
        st.error("Supabase credentials not found. Please add them.")
        st.stop()

def fetch_all_users_for_auth() -> dict:
    # ... (no changes to this function)
def register_user(username, name, email, hashed_password) -> bool:
    # ... (no changes to this function)
def get_user_id_by_username(username: str) -> str | None:
    # ... (no changes to this function)
def upload_receipt(uploaded_file, username: str) -> str | None:
    # ... (no changes to this function)
def add_report(user_id, report_name, total_amount) -> str | None:
    # ... (no changes to this function)

def add_expense_item(report_id, expense_date, vendor, description, amount, receipt_path=None, ocr_text=None, gst_amount=None, pst_amount=None, hst_amount=None, line_items=None):
    supabase = init_connection()
    try:
        supabase.table('expenses').insert({
            "report_id": report_id, "expense_date": str(expense_date), "vendor": vendor,
            "description": description, "amount": amount, "receipt_path": receipt_path,
            "ocr_text": ocr_text, "gst_amount": gst_amount, "pst_amount": pst_amount,
            "hst_amount": hst_amount, 
            "line_items": json.dumps(line_items) if line_items else None # Correctly handle line_items
        }).execute()
        return True
    except Exception as e:
        st.error(f"Error saving item '{description}': {e}")
        return False

def get_reports_for_user(user_id):
    # ... (no changes to this function)
def get_expenses_for_report(report_id):
    # ... (no changes to this function)
def get_receipt_public_url(path: str) -> str:
    # ... (no changes to this function)
