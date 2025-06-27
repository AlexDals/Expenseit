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
role = st.session_state.get("role", "logged_out")
pages = PAGES_FOR_ROLES.get(role, PAGES_FOR_ROLES["logged_out"])

st.sidebar.header("Navigation")
for label, fname in pages:
    # hide any file starting with "_" 
    if fname.startswith("_"):
        continue
    if st.sidebar.button(label):
        st.switch_page(f"pages/{fname}")




# Build the navigation dictionary based on role
# app.py (or wherever you kept it)

# Map roles to a list of (label, filename) tuples
PAGES_FOR_ROLES = {
    "admin": [
        ("Dashboard",             "2_Dashboard.py"),
        ("New Report",            "3_New_Report.py"),
        ("View Reports",          "4_View_Reports.py"),
        ("User Management",       "6_Users.py"),
        ("Category Management",   "9_Category_Management.py"),
        # these are hidden in the sidebar because of the leading "_"
        ("Add User",              "_7_Add_User.py"),
        ("Edit User",             "_8_Edit_User.py"),
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


# Select the correct list of pages
if is_logged_in:
    nav_pages = PAGES_FOR_ROLES.get(user_role, PAGES_FOR_ROLES["user"])
else:
    nav_pages = PAGES_FOR_ROLES["logged_out"]

# Create and run the navigation
pg = st.navigation(nav_pages)
pg.run()
