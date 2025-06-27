import streamlit as st
from streamlit_authenticator import Authenticate
from utils import supabase_utils as su
from utils.nav_utils import PAGES_FOR_ROLES

st.set_page_config(layout="wide", page_title="Expense Reporting")

# --- USER AUTHENTICATION SETUP ---
if "authenticator" not in st.session_state:
    creds = su.fetch_all_users_for_auth()
    cfg   = st.secrets.get("cookie", {})
    auth  = Authenticate(
        creds,
        cfg.get("name",        "cookie_name"),
        cfg.get("key",         "random_key"),
        cfg.get("expiry_days", 30),
    )
    st.session_state["authenticator"]    = auth
    st.session_state["user_credentials"] = creds

# --- POPULATE ROLE & USER_ID AFTER LOGIN ---
if st.session_state.get("authentication_status"):
    if "role" not in st.session_state or st.session_state.role is None:
        uname = st.session_state.get("username", "")
        info  = st.session_state["user_credentials"]["usernames"].get(uname, {})
        st.session_state["role"]    = info.get("role")
        st.session_state["user_id"] = info.get("id")

# --- CUSTOM SIDEBAR NAVIGATION BASED ON ROLE ---
role = st.session_state.get("role", "logged_out")
st.sidebar.header("Navigation")
for label, fname in PAGES_FOR_ROLES.get(role, PAGES_FOR_ROLES["logged_out"]):
    if st.sidebar.button(label):
        st.switch_page(f"pages/{fname}")
