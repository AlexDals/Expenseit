import streamlit as st
from utils import supabase_utils as su
from streamlit_authenticator import Authenticate

# --- PAGE CONFIGURATION ---
# This MUST be the first Streamlit command.
st.set_page_config(layout="wide", page_title="Expense Reporting")

# --- USER AUTHENTICATION SETUP ---
# We initialize the authenticator once and store it in session state
# to ensure it persists across page navigations.
if 'authenticator' not in st.session_state:
    try:
        user_credentials = su.fetch_all_users_for_auth()
        cookie_config = st.secrets.get("cookie", {})
        
        authenticator = Authenticate(
            user_credentials,
            cookie_config['name'],
            cookie_config['key'],
            cookie_config.get('expiry_days', 30),
        )
        st.session_state['authenticator'] = authenticator
    except Exception as e:
        st.error(f"An error occurred during authentication setup: {e}")
        st.stop()
else:
    authenticator = st.session_state['authenticator']

# --- PROGRAMMATIC NAVIGATION ---
# Define all possible pages in your app.
login_page = st.Page("pages/1_Login.py", title="Login", icon="🔑", default=True)
dashboard_page = st.Page("pages/2_Dashboard.py", title="Dashboard", icon="🏠")
new_report_page = st.Page("pages/3_New_Report.py", title="New Report", icon="📄")
view_reports_page = st.Page("pages/4_View_Reports.py", title="View Reports", icon="🗂️")
register_page = st.Page("pages/5_Register.py", title="Register", icon="🔑")
admin_page = st.Page("pages/6_User_Management.py", title="User Management", icon="⚙️")

# Define the navigation structure based on the user's login status and role.
nav_pages = []
if st.session_state.get("authentication_status"):
    # If the user is logged in
    # Manually set the role if it's not already in the session state
    if 'role' not in st.session_state or st.session_state.role is None:
        st.session_state["role"] = su.get_user_role(st.session_state.get("username"))

    nav_pages = [dashboard_page, new_report_page, view_reports_page]
    if st.session_state.get("role") == 'admin':
        nav_pages.append(admin_page)
else:
    # If the user is logged out
    nav_pages = [login_page, register_page]

# Create the navigation object from the filtered list of pages
pg = st.navigation(nav_pages)

# Run the app by calling the navigation object's run() method
pg.run()
