# File: pages/1_Login.py

import streamlit as st
from utils import supabase_utils as su
from streamlit_authenticator import Authenticate
from utils.ui_utils import hide_streamlit_pages_nav

# Hide Streamlit’s built-in pages nav immediately
hide_streamlit_pages_nav()

st.set_page_config(page_title="Login", layout="wide")

st.title("Employee Expense Reporting")
st.write("Please log in to access your dashboard.")

# Initialize authenticator if missing
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

# Show login form in the main area (use "main" as the location name)
name, auth_status, username = authenticator.login("Login", "main")

if auth_status:
    # Store user info & redirect
    st.session_state["name"]                  = name
    st.session_state["username"]              = username
    st.session_state["authentication_status"] = True
    st.success(f"Welcome, {name}! Redirecting…")
    st.experimental_rerun()

elif auth_status is False:
    st.error("Username/password is incorrect.")

elif auth_status is None:
    st.warning("Please enter your username and password.")
