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
authenticator.login(location="main")

# Read back the results
auth_status = st.session_state.get("authentication_status")
name        = st.session_state.get("name")
username    = st.session_state.get("username")

if auth_status:
    creds_map = st.session_state["user_credentials"]["usernames"]
    user_entry = creds_map.get(username, {})

    st.session_state["name"]                  = name
    st.session_state["username"]              = username
    st.session_state["authentication_status"] = True
    st.session_state["role"]                  = user_entry.get("role")
    st.session_state["user_id"]               = user_entry.get("id")

    st.success(f"Welcome, {name}! Redirecting…")
    st.switch_page("pages/2_Dashboard.py")

elif auth_status is False:
    st.error("Username/password is incorrect.")

else:  # auth_status is None
    st.warning("Please enter your username and password.")
