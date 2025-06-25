import streamlit as st
from utils import supabase_utils as su
import bcrypt

st.title("➕ Add New User")

# --- Authentication Guard ---
if not st.session_state.get("authentication_status") or st.session_state.get("role") != 'admin':
    st.error("You do not have permission to access this page.")
    st.stop()

with st.form("admin_create_user_form"):
    st.subheader("New User Details")
    
    col1, col2 = st.columns(2)
    with col1:
        new_name = st.text_input("Full Name*")
        new_username = st.text_input("Username* (no spaces)")
        new_email = st.text_input("Email*")
    with col2:
        new_password = st.text_input("Set Initial Password*", type="password")
        new_role = st.selectbox("Assign Role*", options=["user", "approver", "admin"])

    st.markdown("---")
    create_submitted = st.form_submit_button("Create User", use_container_width=True)

    if create_submitted:
        if not all([new_email, new_name, new_username, new_password, new_role]):
            st.error("Please fill out all required fields.")
        else:
            with st.spinner("Creating user..."):
                password_bytes = new_password.encode('utf-8')
                hashed_password = bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode('utf-8')
                
                if su.register_user(new_username, new_name, new_email, hashed_password, new_role):
                    st.success(f"User '{new_username}' created successfully!")
                    st.info("Returning to user list...")
                    st.switch_page("pages/6_Users.py")
                else:
                    # The register_user function will display a specific error
                    pass

st.page_link("pages/6_Users.py", label="← Back to User Management", icon="⚙️")
