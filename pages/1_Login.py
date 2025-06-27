# File: pages/1_Login.py

import streamlit as st
from utils.ui_utils import hide_streamlit_pages_nav
from utils import supabase_utils as su
from streamlit_authenticator import Authenticate

# ─── Hide Streamlit’s built-in pages nav ───────────────────────
hide_streamlit_pages_nav()

# ─── Page config ───────────────────────────────────────────────
st.set_page_config(page_title="Login", layout="wide")

# ─── Header ────────────────────────────────────────────────────
st.title("Employee Expense Reporting")
st.write("Please log in to access your dashboard.")

# ─── Initialize or retrieve the authenticator ─────────────────
if "authenticator" not in st.session_state:
    # Fetch credentials for all users
    creds = su.fetch_all_users_for_auth()
    # Cookie configuration from secrets (name, key, expiry_days)
    cfg = st.secrets.get("cookie", {})
    authenticator = Authenticate(
        creds,
        cfg.get("name", "some_cookie_name"),
        cfg.get("key", "some_random_key"),
        cfg.get("expiry_days", 30),
    )
    # Store in session state
    st.session_state["authenticator"]     = authenticator
    st.session_state["user_credentials"]  = creds

authenticator = st.session_state["authenticator"]

# ─── Show the login form and capture the result ───────────────
name, authentication_status, username = authenticator.login("Login", "main")

# ─── Handle login result ───────────────────────────────────────
if authentication_status:
    # Populate session state
    st.session_state["name"]                   = name
    st.session_state["username"]               = username
    st.session_state["authentication_status"]  = True

    # Redirect to Dashboard page
    st.success(f"Welcome, {name}! Redirecting to your dashboard…")
    st.experimental_rerun()

elif authentication_status is False:
    st.error("Username/password is incorrect.")

# If authentication_status is None (i.e. form not yet submitted), do nothing.
