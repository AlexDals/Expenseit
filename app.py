# File: app.py

import streamlit as st
from utils import supabase_utils as su
from streamlit_authenticator import Authenticate

# ─── PAGE CONFIGURATION ───────────────────────────────────────────
st.set_page_config(layout="wide", page_title="Expense Reporting")

# ─── HIDE STREAMLIT’S AUTO-DISCOVERED PAGES NAV ────────────────────
st.markdown(
    """
    <style>
      /* Hide the default pages list in the sidebar */
      div[data-testid="stSidebarNav"] {
        display: none;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

# ─── USER AUTHENTICATION SETUP ──────────────────────────────────────
if 'authenticator' not in st.session_state:
    try:
        user_credentials = su.fetch_all_users_for_auth()
        cookie_config   = st.secrets.get("cookie", {})
        authenticator   = Authenticate(
            user_credentials,
            cookie_config.get("name",       "some_cookie_name"),
            cookie_config.get("key",        "some_random_key"),
            cookie_config.get("expiry_days", 30),
        )
        st.session_state['authenticator']    = authenticator
        st.session_state['user_credentials'] = user_credentials
    except Exception as e:
        st.error(f"Authentication setup failed: {e}")
        st.stop()

# ─── POPULATE ROLE & USER ID AFTER LOGIN ───────────────────────────
if st.session_state.get("authentication_status"):
    if 'role' not in st.session_state or st.session_state.role is None:
        uname = st.session_state.get("username", "")
        creds = st.session_state['user_credentials'].get("usernames", {})
        info  = creds.get(uname, {})
        st.session_state["role"]    = info.get("role")
        st.session_state["user_id"] = info.get("id")

# ─── DEFINE PAGES AVAILABLE FOR EACH ROLE ──────────────────────────
PAGES_FOR_ROLES = {
    "admin": [
        ("Dashboard",             "2_Dashboard.py"),
        ("New Report",            "3_New_Report.py"),
        ("View Reports",          "4_View_Reports.py"),
        ("User Management",       "6_Users.py"),
        ("Category Management",   "9_Category_Management.py"),
        ("Department Maintenance","9_Department_Maintenance.py"),
        # These exist on disk but will be hidden from the sidebar
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

# ─── DETERMINE CURRENT ROLE & LOGIN STATUS ────────────────────────
is_logged_in = st.session_state.get("authentication_status", False)
role         = st.session_state.get("role", "logged_out")

# ─── RENDER CUSTOM SIDEBAR NAVIGATION ─────────────────────────────
st.sidebar.header("Navigation")
for label, fname in PAGES_FOR_ROLES.get(role, PAGES_FOR_ROLES["logged_out"]):
    # never show underscore‐prefixed pages in the sidebar
    if fname.startswith("_"):
        continue
    if st.sidebar.button(label):
        st.switch_page(f"pages/{fname}")

# ─── NOTE ───────────────────────────────────────────────────────────
# From here, each page (1_Login.py, 2_Dashboard.py, etc.)
# will handle its own rendering. We’ve removed all st.Page() calls
# and hidden the default menu, so only your custom sidebar appears.
