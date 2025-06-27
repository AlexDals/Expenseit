# File: pages/1_Login.py

import streamlit as st
from utils import supabase_utils as su
from streamlit_authenticator import Authenticate
from utils.ui_utils import hide_streamlit_pages_nav

# Hide Streamlit’s built-in pages nav immediately
hide_streamlit_pages_nav()

# Page configuration
st.set_page_config(page_title="Login", layout="wide")

st.title("Employee Expense Reporting")
st.write("Please log in to access your dashboard.")

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

authenticator = st.session_state["authenticator"]

# Render the login form in the main area
# (this will set `st.session_state["authentication_status"]`, `"name"`, and `"username"`)
authenticator.login(location="main")

# Check authentication status from session_state
auth_status = st.session_state.get("authentication_status")

if auth_status:
    # Successful login → redirect to Dashboard
    st.success(f"Welcome, {st.session_state.get('name')}! Redirecting…")
    st.switch_page("pages/2_Dashboard.py")  # Dashboard page :contentReference[oaicite:6]{index=6}

elif auth_status is False:
    st.error("Username/password is incorrect.")

else:
    st.warning("Please enter your username and password.")
