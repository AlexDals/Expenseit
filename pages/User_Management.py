import streamlit as st
from utils import supabase_utils as su
import pandas as pd
import streamlit_authenticator as stauth
import re
import bcrypt

st.set_page_config(layout="wide")
st.title("⚙️ User Management")

# --- Authentication and Role Check ---
if 'authentication_status' not in st.session_state or not st.session_state['authentication_status']:
    st.warning("Please log in to access this page.")
    st.stop()
elif st.session_state.get("role") != 'admin':
    st.error("You do not have permission to access this page.")
    st.stop()

# --- NEW: Admin User Creation Form ---
with st.expander("Create a New User", expanded=False):
    with st.form("admin_create_user_form", clear_on_submit=True):
        st.subheader("New User Details")
        new_name = st.text_input("Full Name*")
        new_username = st.text_input("Username* (no spaces)")
        new_email = st.text_input("Email*")
        new_password = st.text_input("Password*", type="password")
        new_role = st.selectbox("Assign Role*", options=["user", "approver", "admin"])
        
        create_submitted = st.form_submit_button("Create User")

        if create_submitted:
            if not all([new_email, new_name, new_username, new_password, new_role]):
                st.error("Please fill out all fields to create a user.")
            else:
