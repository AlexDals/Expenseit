import streamlit as st
from utils import supabase_utils as su
from streamlit_authenticator import Authenticate

# ─── PAGE CONFIGURATION & HIDE BUILT-IN NAV ─────────────
st.set_page_config(layout="wide", page_title="Expense Reporting")
st.markdown(
    """
    <style>
      /* Hide built-in multi-page nav and sidebar nav container */
      nav[aria-label="App pages"],
      div[data-testid="stSidebarNav"] {
        display: none !important;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

# ─── AUTHENTICATION SETUP ──────────────────────────────────
if "authenticator" not in st.session_state:
    try:
        creds = su.fetch_all_users_for_auth()
        cfg   = st.secrets.get("cookie", {})
        auth  = Authenticate(
            creds,
            cfg.get("name",        "some_cookie_name"),
            cfg.get("key",         "some_random_key"),
            cfg.get("expiry_days", 30),
        )
        st.session_state["authenticator"]    = auth
        st.session_state["user_credentials"] = creds
    except Exception as e:
        st.error(f"Auth setup failed: {e}")
        st.stop()

# ─── POPULATE ROLE & USER_ID AFTER LOGIN ───────────────────
if st.session_state.get("authentication_status"):
    if "role" not in st.session_state or st.session_state.role is None:
        uname = st.session_state.get("username", "")
        users = st.session_state["user_credentials"].get("usernames", {})
        info  = users.get(uname, {})
        st.session_state["role"]    = info.get("role")
        st.session_state["user_id"] = info.get("id")

# ─── PAGES FOR ROLES ────────────────────────────────────────
PAGES_FOR_ROLES = {
    "admin": [
        ("Dashboard",             "2_Dashboard.py"),
        ("New Report",            "3_New_Report.py"),
        ("View Reports",          "4_View_Reports.py"),
        ("User Management",       "6_Users.py"),
        ("Category Management",   "9_Category_Management.py"),
        ("Department Maintenance","9_Department_Maintenance.py"),
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

# ─── BUILD CUSTOM SIDEBAR BASED ON ROLE ────────────────────
role = st.session_state.get("role", "logged_out")
st.sidebar.header("Navigation")
for label, fname in PAGES_FOR_ROLES.get(role, PAGES_FOR_ROLES["logged_out"]):
    if fname.startswith("_"):
        continue
    if st.sidebar.button(label):
        st.switch_page(f"pages/{fname}")
