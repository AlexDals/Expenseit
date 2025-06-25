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
        st.error("Supabase credentials not found.")
        st.stop()

# --- THIS FUNCTION IS MODIFIED ---
def get_all_users():
    """Fetches all user data, joining the category name for their default category."""
    supabase = init_connection()
    try:
        # Selects the new default_category_id and joins to get the category name
        response = supabase.table('users').select("id, username, name, email, role, approver_id, default_category:categories(id, name)").execute()
        
        users = response.data
        for user in users:
            if user.get('default_category') and isinstance(user['default_category'], dict):
                user['default_category_name'] = user['default_category'].get('name')
                user['default_category_id'] = user['default_category'].get('id')
            else:
                user['default_category_name'] = None
                user['default_category_id'] = None
            user.pop('default_category', None) # Clean up the nested object

        return pd.DataFrame(users)
    except Exception as e:
        st.error(f"Error fetching all users: {e}")
        return pd.DataFrame()

# --- THIS FUNCTION IS MODIFIED ---
def update_user_details(user_id, role, approver_id, default_category_id):
    """Updates a user's role, assigned approver, and default category."""
    supabase = init_connection()
    try:
        supabase.table('users').update({
            "role": role,
            "approver_id": approver_id,
            "default_category_id": default_category_id # Use new category ID field
        }).eq('id', user_id).execute()
        return True
    except Exception as e:
        st.error(f"Error updating user details: {e}")
        return False

# --- THIS FUNCTION IS MODIFIED ---
def get_reports_for_approver(approver_id):
    """Fetches reports for an approver based on their default category."""
    supabase = init_connection()
    try:
        # 1. Get the approver's default category ID
        approver_response = supabase.table('users').select('default_category_id').eq('id', approver_id).maybe_single().execute()
        if not approver_response.data or not approver_response.data.get('default_category_id'):
            return pd.DataFrame()
        
        approver_category_id = approver_response.data['default_category_id']

        # 2. Find all users who share that same default category (excluding the approver)
        employees_response = supabase.table('users').select('id').eq('default_category_id', approver_category_id).neq('id', approver_id).execute()
        employee_ids = [user['id'] for user in employees_response.data]
        
        if not employee_ids:
            return pd.DataFrame()

        # 3. Fetch reports for those employees
        reports_response = supabase.table('reports').select("*, user:users!left(name)").in_('user_id', employee_ids).order('submission_date', desc=True).execute()
        return pd.DataFrame(reports_response.data)
    except Exception as e:
        st.error(f"Error fetching reports for approver: {e}")
        return pd.DataFrame()

# ... (All other functions from the last working version are included below for completeness) ...
def fetch_all_users_for_auth():
    supabase = init_connection()
    try:
        response = supabase.table('users').select("id, username, email, name, hashed_password, role").execute()
        users_data = response.data
        credentials = {"usernames": {}}
        for user in users_data:
            credentials["usernames"][user["username"]] = {"id": user["id"], "email": user["email"], "name": user["name"], "password": user["hashed_password"], "role": user["role"]}
        return credentials
    except Exception as e:
        st.error(f"Error fetching users: {e}"); return {"usernames": {}}

def register_user(username, name, email, hashed_password, role='user'):
    supabase = init_connection()
    try:
        if supabase.table('users').select('id', count='exact').eq('username', username).execute().count > 0:
            st.error("Username already taken."); return False
        supabase.table('users').insert({"username": username, "name": name, "email": email, "hashed_password": hashed_password, "role": role}).execute()
        return True
    except Exception as e:
        st.error(f"Error during registration: {e}"); return False

def get_user_role(username: str):
    supabase = init_connection()
    try:
        response = supabase.table('users').select('role').eq('username', username).execute()
        return response.data[0].get('role') if response.data else None
    except Exception as e:
        st.error(f"Error fetching user role: {e}"); return None

def get_all_approvers():
    supabase = init_connection()
    try:
        response = supabase.table('users').select("id, name").in_('role', ['approver', 'admin']).execute()
        return response.data
    except Exception as e:
        st.error(f"Error fetching approvers: {e}"); return []
