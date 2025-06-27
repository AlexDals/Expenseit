# File: app.py

import streamlit as st
from utils import supabase_utils as su
from streamlit_authenticator import Authenticate

# ─── PAGE CONFIG ─────────────────────────────────────────────
st.set_page_config(layout="wide", page_title="Expense Reporting")

# ─── CSS TO HIDE STREAMLIT’S BUILT-IN PAGES NAV ───────────────
# This hides the <nav aria-label="App pages"> and the data-testid sidebar nav
st.markdown(
    """
    <style>
      /* Hide the default multi-page navigation */
      nav[aria-label="App pages"],
      div[data-testid="stSidebarNav"] {
        display: none !important;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

# ─── USER AUTHENTICATION SETUP ────────────────────────────────
if "authenticator" not in st.session_state:
    try:
        user_credentials = su.fetch_all_users_for_auth()
        cookie_config   = st.secrets.get("cookie", {})
        authenticator   = Authenticate(
            user_credentials,
            cookie_config.get("name",        "some_cookie_name"),
            cookie_config.get("key",         "some_random_key"),
            cookie_config.get("expiry_days", 30),
        )
        st.session_state["authenticator"]     = authenticator
        st.session_state["user_credentials"]  = user_credentials
    except Exception as e:
        st.error(f"Authentication setup failed: {e}")
        st.stop()

# ─── POPULATE ROLE & USER_ID AFTER LOGIN ───────────────────────
if st.session_state.get("authentication_status"):
    if "role" not in st.session_state or st.session_state.role is None:
        uname = st.session_state.get("username", "")
        users = st.session_state["user_credentials"].get("usernames", {})
        info  = users.get(uname, {})
        st.session_state["role"]    = info.get("role")
        st.session_state["user_id"] = info.get("id")

# ─── DEFINE PAGES FOR EACH ROLE ───────────────────────────────
PAGES_FOR_ROLES = {
    "admin": [
        ("Dashboard",             "2_Dashboard.py"),
        ("New Report",            "3_New_Report.py"),
        ("View Reports",          "4_View_Reports.py"),
        ("User Management",       "6_Users.py"),
        ("Category Management",   "9_Category_Management.py"),
        ("Department Maintenance","9_Department_Maintenance.py"),
        # hidden pages (exist on disk but never in sidebar)
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

# ─── DETERMINE CURRENT ROLE & LOGIN STATUS ────────────────────
is_logged_in = st.session_state.get("authentication_status", False)
role         = st.session_state.get("role", "logged_out")

# ─── BUILD YOUR CUSTOM SIDEBAR MENU ───────────────────────────
st.sidebar.header("Navigation")
for label, fname in PAGES_FOR_ROLES.get(role, PAGES_FOR_ROLES["logged_out"]):
    # never show underscore- prefixed pages in the sidebar
    if fname.startswith("_"):
        continue
    if st.sidebar.button(label):
        st.switch_page(f"pages/{fname}")

# ─── YOUR MAIN APP LOGIC CONTINUES VIA pages/*.py ─────────────
# At this point, Streamlit will load whichever pages/*.py 
# corresponds to the URL (Login, Dashboard, etc.).  
