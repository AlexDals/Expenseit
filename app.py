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
            user_credentials = st.session_state.get('user_credentials', {})
            user_details = user_credentials.get("usernames", {}).get(username, {})
            st.session_state["role"] = user_details.get("role")
            st.session_state["user_id"] = user_details.get("id")

# --- PROGRAMMATIC NAVIGATION ---
is_logged_in = st.session_state.get("authentication_status")
user_role = st.session_state.get("role")




# Build the navigation dictionary based on role
PAGES_FOR_ROLES = {
    "admin": [dashboard_page, new_report_page, view_reports_page, users_page, category_management_page, add_user_page, edit_user_page],
    "approver": [dashboard_page, new_report_page, view_reports_page],
    "user": [dashboard_page, new_report_page, view_reports_page],
    "logged_out": [login_page, register_page]
}

# Select the correct list of pages
if is_logged_in:
    nav_pages = PAGES_FOR_ROLES.get(user_role, PAGES_FOR_ROLES["user"])
else:
    nav_pages = PAGES_FOR_ROLES["logged_out"]

# Create and run the navigation
pg = st.navigation(nav_pages)
pg.run()
