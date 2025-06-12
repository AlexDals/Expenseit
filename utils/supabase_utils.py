import streamlit as st
from supabase import create_client, Client
import pandas as pd
from datetime import datetime
import os
import json
import xml.etree.ElementTree as ET
from xml.dom import minidom

@st.cache_resource
def init_connection():
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key)
    except KeyError:
        st.error("Supabase credentials not found.")
        st.stop()

# --- FUNCTION MODIFIED ---
def get_reports_for_approver(approver_id):
    """
    Fetches reports for an approver based on department.
    An approver can see all reports from users in their own department.
    """
    supabase = init_connection()
    try:
        # 1. Get the approver's department
        approver_dept_response = supabase.table('users').select('department').eq('id', approver_id).maybe_single().execute()
        if not approver_dept_response.data or not approver_dept_response.data.get('department'):
            st.warning("Your user profile does not have a department assigned. You cannot see any reports to approve.")
            return pd.DataFrame()
        
        approver_department = approver_dept_response.data['department']

        # 2. Find all users in that same department (excluding the approver themselves)
        employees_response = supabase.table('users').select('id').eq('department', approver_department).neq('id', approver_id).execute()
        employee_ids = [user['id'] for user in employees_response.data]
        
        if not employee_ids:
            return pd.DataFrame()

        # 3. Fetch reports for those employees
        reports_response = supabase.table('reports').select("*, user:users!left(name)").in_('user_id', employee_ids).order('submission_date', desc=True).execute()
        return pd.DataFrame(reports_response.data)
    except Exception as e:
        st.error(f"Error fetching reports for approver: {e}")
        return pd.DataFrame()

# --- FUNCTION MODIFIED ---
def get_all_users():
    """Fetches all user data for the management page, including department."""
    supabase = init_connection()
    try:
        response = supabase.table('users').select("id, username, name, email, role, approver_id, department").execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"Error fetching all users: {e}")
        return pd.DataFrame()

# --- FUNCTION MODIFIED ---
def update_user_details(user_id, role, approver_id, department):
    """Updates a user's role, assigned approver, and department."""
    supabase = init_connection()
    try:
        supabase.table('users').update({
            "role": role,
            "approver_id": approver_id,
            "department": department
        }).eq('id', user_id).execute()
        return True
    except Exception as e:
        st.error(f"Error updating user details: {e}")
        return False
        
# ... (The rest of your functions in this file remain unchanged) ...
