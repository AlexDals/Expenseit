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

# --- Admin User Creation Form (This can be kept as a separate, explicit creation method) ---
with st.expander("➕ Create a New User (Recommended)"):
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
st.info("You can edit, add, or delete users directly in the grid below. Click 'Save All Changes' when you are done.")

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
else:
    # Prepare dataframe for editing
    all_users_df['approver_name'] = all_users_df['approver_id'].map(approver_map).fillna("")
    all_users_df['default_category_name'] = all_users_df['default_category_id'].map(category_map).fillna("")

    # Store the original dataframe in session state to compare against edits
    if 'original_users_df' not in st.session_state:
        st.session_state.original_users_df = all_users_df.copy()

    edited_df = st.data_editor(
        all_users_df,
        column_config={
            "id": None, "approver_id": None, "default_category_id": None, 
            "username": "Username", "name": "Full Name", "email": "Email",
            "role": st.column_config.SelectboxColumn("Role", options=["user", "approver", "admin"], required=True),
            "approver_name": st.column_config.SelectboxColumn("Approver", options=approver_options),
            "default_category_name": st.column_config.SelectboxColumn("Default Category", options=category_options)
        },
        num_rows="dynamic", # Allow adding and deleting
        hide_index=True,
        key="user_editor"
    )

    if st.button("Save All User Changes"):
        with st.spinner("Saving changes..."):
            original_df = st.session_state.original_users_df
            
            # Convert to sets of IDs for finding added/deleted rows
            original_ids = set(original_df['id'].dropna())
            edited_ids = set(pd.DataFrame(edited_df)['id'].dropna())
            
            all_success = True
            
            # Process Deletions
            deleted_ids = original_ids - edited_ids
            for user_id in deleted_ids:
                st.warning(f"Deleting user with ID: {user_id}. This action is not yet implemented.")
                # To implement: su.delete_user(user_id)
            
            # Process Additions and Updates
            for user_data in edited_df:
                user_id = user_data.get('id')
                
                # Convert friendly names back to IDs for saving
                approver_id = approver_name_to_id.get(user_data['approver_name'])
                category_id = category_name_to_id.get(user_data['default_category_name'])

                # If ID is missing, it's a new user
                if pd.isna(user_id):
                    st.warning("Adding new users directly in the grid is not supported yet. Please use the 'Create a New User' form above.")
                    # To implement: Add a temporary password field, hash it, and call su.register_user(...)
                    continue
                
                # Check for updates
                original_row = original_df[original_df['id'] == user_id]
                if not original_row.empty:
                    # Compare each value to see if an update is needed
                    # (This is complex, a simpler approach is to just update all)
                    if not su.update_user_details(user_id, user_data['role'], approver_id, category_id):
                        all_success = False
            
            if all_success:
                st.success("All changes saved successfully!")
                st.session_state.original_users_df = pd.DataFrame(edited_df) # Update the baseline
                st.rerun()
            else:
                st.error("One or more changes could not be saved.")
