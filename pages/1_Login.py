import streamlit as st
from utils.nav_utils import filter_pages_by_role
filter_pages_by_role()

st.set_page_config(layout="wide", page_title="Login")
st.title("Employee Expense Reporting")
st.write("Please log in to access your dashboard.")

# --- Retrieve the authenticator object from session state ---
authenticator = st.session_state.get("authenticator")
if not authenticator:
    st.error("Authentication system not initialized. Please run the main app.py file.")
    st.stop()

# --- Render the login form ---
authenticator.login()

# --- Display messages based on login status ---
if st.session_state.get("authentication_status") is False:
    st.error("Username/password is incorrect.")
