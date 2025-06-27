# File: pages/1_Login.py

import streamlit as st
from utils import supabase_utils as su
from streamlit_authenticator import Authenticate
from utils.ui_utils import hide_streamlit_pages_nav

# ─── Permanently hide Streamlit’s built-in pages nav ─────────────
hide_streamlit_pages_nav()

# ─── Page configuration ──────────────────────────────────────────
st.set_page_config(page_title="Login", layout="wide")

# ─── Header ──────────────────────────────────────────────────────
st.title("Employee Expense Reporting")
st.write("Please log in to access your dashboard.")

# ─── Ensure the authenticator is initialized ────────────────────
if "authenticator" not in st.session_state:
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

authenticator = st.session_state["authenticator"]

# ─── Show login form ─────────────────────────────────────────────
# Pass the form name then keyword‐arg location
name, authentication_status, username = authenticator.login(
    "Login", location="main"
)

# ─── Handle login result ────────────────────────────────────────
if authentication_status:
    # Store in session state
    st.session_state["name"]                  = name
    st.session_state["username"]              = username
    st.session_state["authentication_status"] = True

    # Success message and redirect to Dashboard
    st.success(f"Welcome, {name}! Redirecting to your dashboard…")
    st.experimental_rerun()

elif authentication_status is False:
    st.error("Username/password is incorrect.")
