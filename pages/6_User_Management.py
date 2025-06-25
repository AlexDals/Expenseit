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

# Store the original dataframe in session state to compare against edits
if 'original_users_df' not in st.session_state:
    st.session_state.original_users_df = all_users_df.copy()

# --- The Data Editor ---
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
    num_rows="dynamic",
    key="user_editor"
)

# --- DEFINITIVE SAVE LOGIC ---
if st.button("Save All User Changes"):
    with st.spinner("Saving changes..."):
        all_success = True
        
        # Convert the potentially edited dataframe back to a list of dictionaries
        edited_users_list = edited_df.to_dict('records')
        
        for user_data in edited_users_list:
            user_id = user_data.get('id')
            
            # This handles newly added rows that don't have an ID yet
            if pd.isna(user_id):
                st.warning("Adding new users directly in the grid is not yet supported. Please use the 'Create a New User' form above.")
                continue

            # Convert friendly names back to IDs for saving
            approver_id = approver_name_to_id.get(user_data['approver_name'])
            category_id = category_name_to_id.get(user_data['default_category_name'])
            
            # Call the updated details function
            if not su.update_user_details(user_id, user_data['role'], approver_id, category_id):
                all_success = False
        
        if all_success:
            st.success("All changes saved successfully!")
            # Update the baseline state and rerun
            st.session_state.original_users_df = pd.DataFrame(edited_df)
            st.rerun()
        else:
            st.error("One or more changes could not be saved.")
