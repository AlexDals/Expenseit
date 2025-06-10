import streamlit as st
from supabase import create_client, Client
import pandas as pd
from datetime import datetime
import os
import json

@st.cache_resource
def init_connection() -> Client:
    """Initializes and returns a Supabase client, cached for performance."""
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key)
    except KeyError:
        st.error("Supabase credentials not found in secrets.toml. Please add them.")
        st.stop()

def fetch_all_users_for_auth() -> dict:
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

def register_user(username, name, email, hashed_password) -> bool:
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

def get_user_id_by_username(username: str) -> str | None:
    """Fetches the UUID for a given username."""
    supabase = init_connection()
    try:
        response = supabase.table('users').select('id').eq('username', username).execute()
        return response.data[0]['id'] if response.data else None
    except Exception as e:
        st.error(f"Error fetching user ID: {e}")
        return None

def upload_receipt(uploaded_file, username: str) -> str | None:
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

def add_report(user_id, report_name, total_amount) -> str | None:
    """Adds a new report header to the database."""
    supabase = init_connection()
    try:
        response = supabase.table('reports').insert({
            "user_id": user_id,
            "report_name": report_name,
            "submission_date": datetime.now().isoformat(),
            "total_amount": total_amount
