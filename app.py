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
else:
    authenticator = st.session_state['authenticator']

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

login_page = st.Page("pages/1_Login.py", title="Login", icon="🔑", default=(not is_logged_in))
dashboard_page = st.Page("pages/2_Dashboard.py", title="Dashboard", icon="🏠", default=is_logged_in)
new_report_page = st.Page("pages/3_New_Report.py", title="New Report", icon="📄")
view_reports_page = st.Page("pages/4_View_Reports.py", title="View Reports", icon="🗂️")
register_page = st.Page("pages/5_Register.py", title="Register", icon="🔑")
user_management_page = st.Page("pages/6_User_Management.py", title="User Management", icon="⚙️")
category_management_page = st.Page("pages/7_Category_Management.py", title="Category Management", icon="📈")

if is_logged_in:
    nav_pages = [dashboard_page, new_report_page, view_reports_page]
    if st.session_state.get("role") == 'admin':
        nav_pages.append(user_management_page)
        nav_pages.append(category_management_page)
else:
    nav_pages = [login_page, register_page]

pg = st.navigation(nav_pages)
pg.run()
