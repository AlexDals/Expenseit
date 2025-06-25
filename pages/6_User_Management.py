import streamlit as st
from utils import supabase_utils as su
import pandas as pd
import bcrypt

st.title("⚙️ User Management")

# --- Authentication Guard ---
if not st.session_state.get("authentication_status") or st.session_state.get("role") != 'admin':
    st.error("You do not have permission to access this page.")
    st.stop()

# --- Admin User Creation Form ---
with st.expander("➕ Create a New User"):
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
                st.error("Please fill out all fields.")
            else:
                hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                if su.register_user(new_username, new_name, new_email, hashed_password, new_role):
                    st.success(f"User '{new_username}' created successfully!")
                    st.rerun()

st.markdown("---")
st.subheader("Existing Users")
all_users_df = su.get_all_users()

if all_users_df.empty:
    st.warning("No users found.")
    st.stop()

# Display users
for index, user in all_users_df.iterrows():
    with st.container(border=True):
        col1, col2 = st.columns([4, 1])
        with col1:
            st.write(f"**{user['name']}** (`{user['username']}`)")
            st.caption(f"Role: `{user['role']}`")
        with col2:
            # --- DEFINITIVE FIX: Manually construct the URL with query parameters ---
            st.page_link(
                f"pages/8_Edit_User.py?user_id={user['id']}", 
                label="Edit ✏️",
                use_container_width=True
            )
