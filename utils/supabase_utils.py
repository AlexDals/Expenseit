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

# --- THIS FUNCTION IS MODIFIED FOR DEBUGGING ---
def fetch_all_users_for_auth():
    """Fetches all users from the database for the authenticator."""
    supabase = init_connection()
    try:
        st.info("DEBUG: Attempting to fetch users from Supabase...")
        response = supabase.table('users').select("id, username, email, name, hashed_password, role").execute()
        
        # --- TEMPORARY DEBUGGING CODE ---
        st.warning("DEBUG: Raw response from `fetch_all_users_for_auth`:")
        st.write(response)
        # --- END OF DEBUGGING CODE ---

        users_data = response.data
        credentials = {"usernames": {}}
        for user in users_data:
            credentials["usernames"][user["username"]] = {
                "id": user["id"],
                "email": user["email"],
                "name": user["name"],
                "password": user["hashed_password"],
                "role": user["role"]
            }
        return credentials
    except Exception as e:
        st.error(f"Error fetching users: {e}")
        return {"usernames": {}}

def register_user(username, name, email, hashed_password, role='user'):
    supabase = init_connection()
    try:
        if supabase.table('users').select('id', count='exact').eq('username', username).execute().count > 0:
            st.error("Username already taken.")
            return False
        response = supabase.table('users').insert({"username": username, "name": name, "email": email, "hashed_password": hashed_password, "role": role}).execute()
        return True
    except Exception as e:
        st.error(f"Error during registration: {e}")
        return False

def get_user_role(username: str):
    supabase = init_connection()
    try:
        response = supabase.table('users').select('role').eq('username', username).execute()
        return response.data[0].get('role') if response.data else None
    except Exception as e:
        st.error(f"Error fetching user role: {e}")
        return None

# ... (The rest of your utility functions remain unchanged) ...
