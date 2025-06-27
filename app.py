import streamlit as st
from utils import supabase_utils as su
from streamlit_authenticator import Authenticate

# Root app: no filter here, we handle nav in pages themselves.

st.set_page_config(layout="wide", page_title="Expense Reporting")

# --- AUTH SETUP ---
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

if st.session_state.get("authentication_status"):
    if "role" not in st.session_state:
        uname = st.session_state.get("username", "")
        info  = st.session_state["user_credentials"]["usernames"].get(uname, {})
        st.session_state["role"]    = info.get("role")
        st.session_state["user_id"] = info.get("id")

# --- SIDEBAR NAV ---
from utils.nav_utils import PAGES_FOR_ROLES
role = st.session_state.get("role", "logged_out")
st.sidebar.header("Navigation")
for label, fname in PAGES_FOR_ROLES.get(role, PAGES_FOR_ROLES["logged_out"]):
    if st.sidebar.button(label):
        st.switch_page(f"pages/{fname}")
