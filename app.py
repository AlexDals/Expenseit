# File: app.py

import streamlit as st
from utils import supabase_utils as su
from streamlit_authenticator import Authenticate

# --- PAGE CONFIGURATION ---
st.set_page_config(layout="wide", page_title="Expense Reporting")

# --- USER AUTHENTICATION SETUP ---
if 'authenticator' not in st.session_state:
    try:
        user_credentials = su.fetch_all_users_for_auth()
        cookie_config = st.secrets.get("cookie", {})
        authenticator = Authenticate(
            user_credentials,
            cookie_config.get('name', 'some_cookie_name'),
            cookie_config.get('key', 'some_random_key'),
            cookie_config.get('expiry_days', 30),
        )
        st.session_state['authenticator'] = authenticator
        st.session_state['user_credentials'] = user_credentials
    except Exception as e:
        st.error(f"An error occurred during authentication setup: {e}")
        st.stop()

# --- ROLE & ID CHECK AFTER LOGIN ---
if st.session_state.get("authentication_status"):
    if 'role' not in st.session_state or st.session_state.role is None:
        username = st.session_state.get("username")
        if username:
            creds = st.session_state['user_credentials']
            user_details = creds.get("usernames", {}).get(username, {})
            st.session_state["role"] = user_details.get("role")
            st.session_state["user_id"] = user_details.get("id")

# --- PAGES FOR ROLES (defined before use) ---
PAGES_FOR_ROLES = {
    "admin": [
        ("Dashboard",           "2_Dashboard.py"),
        ("New Report",          "3_New_Report.py"),
        ("View Reports",        "4_View_Reports.py"),
        ("User Management",     "6_Users.py"),
        ("Category Management", "9_Category_Management.py"),
        # hidden pages
        ("Add User",            "_7_Add_User.py"),
        ("Edit User",           "_8_Edit_User.py"),
    ],
    "approver": [
        ("Dashboard",   "2_Dashboard.py"),
        ("New Report",  "3_New_Report.py"),
        ("View Reports","4_View_Reports.py"),
    ],
    "user": [
        ("Dashboard",   "2_Dashboard.py"),
        ("New Report",  "3_New_Report.py"),
        ("View Reports","4_View_Reports.py"),
    ],
    "logged_out": [
        ("Login",    "1_Login.py"),
        ("Register", "5_Register.py"),
    ],
}

# --- DETERMINE CURRENT ROLE AND LOGIN STATUS ---
is_logged_in = st.session_state.get("authentication_status", False)
role = st.session_state.get("role", "logged_out")

# --- BUILD NAVIGATION MENU BASED ON ROLE ---
st.sidebar.header("Navigation")
for label, fname in PAGES_FOR_ROLES.get(role, PAGES_FOR_ROLES["logged_out"]):
    # hide any file starting with "_" 
    if fname.startswith("_"):
        continue
    if st.sidebar.button(label):
        st.switch_page(f"pages/{fname}")
