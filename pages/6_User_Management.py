import streamlit as st
from utils import supabase_utils as su
import pandas as pd
import streamlit_authenticator as stauth
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
                st.error("Please fill out all fields to create a user.")
            else:
                try:
                    password_bytes = new_password.encode('utf-8')
                    hashed_password = bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode('utf-8')
                    if su.register_user(new_username, new_name, new_email, hashed_password, new_role):
                        st.success(f"User '{new_username}' created successfully!")
                        st.rerun()
                except Exception as e:
                    st.error(f"A critical error occurred during user creation: {e}")

st.markdown("---")

# --- Existing User Editing Logic ---
st.subheader("Edit Existing Users")
st.info("Edit user roles, approvers, and default categories below.")

# --- Data Preparation for Editor ---
all_users_df = su.get_all_users()
approvers = su.get_all_approvers()
categories = su.get_all_categories()

approver_map = {approver['id']: approver['name'] for approver in approvers}
approver_options = [""] + list(approver_map.values())
approver_name_to_id = {v: k for k, v in approver_map.items()}

category_map = {cat['id']: cat['name'] for cat in categories}
category_options = [""] + list(category_map.values())
category_name_to_id = {v: k for k, v in category_map.items()}

if all_users_df.empty:
    st.warning("No users found.")
    st.stop()

# Prepare dataframe for editing by replacing IDs with human-readable names
all_users_df['approver_name'] = all_users_df['approver_id'].map(approver_map).fillna("")
all_users_df['default_category_name'] = all_users_df['default_category_id'].map(category_map).fillna("")

# --- The Data Editor ---
editor_key = "user_editor"
if editor_key not in st.session_state:
    st.session_state[editor_key] = {"edited_rows": {}}

edited_df = st.data_editor(
    all_users_df,
    column_config={
        "id": None, "approver_id": None, "default_category_id": None, "email": None,
        "username": "Username", "name": "Full Name",
        "role": st.column_config.SelectboxColumn("Role", options=["user", "approver", "admin"], required=True),
        "approver_name": st.column_config.SelectboxColumn("Approver", options=approver_options),
        "default_category_name": st.column_config.SelectboxColumn("Default Category", options=category_options)
    },
    disabled=["username", "name", "email"],
    hide_index=True,
    key=editor_key
)

# --- DEFINITIVE SAVE LOGIC ---
if st.session_state[editor_key].get("edited_rows"):
    if st.button("Save User Changes"):
        with st.spinner("Saving..."):
            edited_rows = st.session_state[editor_key]["edited_rows"]
            all_success = True
            
            for row_index, changes in edited_rows.items():
                user_id = all_users_df.iloc[row_index]['id']
                
                # Get the full row of potentially edited data
                full_edited_row = edited_df.iloc[row_index]
                
                # Convert names back to IDs for saving
                approver_id = approver_name_to_id.get(full_edited_row['approver_name'])
                category_id = category_name_to_id.get(full_edited_row['default_category_name'])
                
                if not su.update_user_details(user_id, full_edited_row['role'], approver_id, category_id):
                    all_success = False
            
            if all_success:
                st.success("All changes saved successfully!")
                # Clear the edited_rows state to hide the button after saving
                st.session_state[editor_key]["edited_rows"] = {}
                st.rerun()
            else:
                st.error("One or more changes could not be saved.")
