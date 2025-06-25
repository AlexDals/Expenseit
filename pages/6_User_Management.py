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
    st.stop()

# Prepare dataframe for editing
all_users_df['approver_name'] = all_users_df['approver_id'].map(approver_map).fillna("")
all_users_df['default_category_name'] = all_users_df['default_category_id'].map(category_map).fillna("")

# --- The Data Editor ---
editor_key = "user_editor"
# Store original df in session state if it's not there
if 'original_users_df' not in st.session_state:
    st.session_state.original_users_df = all_users_df.copy()

edited_df = st.data_editor(
    all_users_df,
    column_config={
        "id": None, "approver_id": None, "default_category_id": None, 
        "username": st.column_config.TextColumn("Username", required=True),
        "name": st.column_config.TextColumn("Full Name", required=True),
        "email": st.column_config.TextColumn("Email", required=True),
        "role": st.column_config.SelectboxColumn("Role", options=["user", "approver", "admin"], required=True),
        "approver_name": st.column_config.SelectboxColumn("Approver", options=approver_options),
        "default_category_name": st.column_config.SelectboxColumn("Default Category", options=category_options)
    },
    num_rows="dynamic",
    hide_index=True,
    key=editor_key
)

# --- DEFINITIVE SAVE LOGIC ---
if st.button("Save All User Changes"):
    with st.spinner("Saving changes..."):
        editor_state = st.session_state[editor_key]
        original_df = st.session_state.original_users_df
        all_success = True
        
        # 1. Process Deletions
        for row_index in editor_state.get("deleted_rows", []):
            user_id_to_delete = original_df.iloc[row_index]['id']
            if not su.delete_user(user_id_to_delete):
                all_success = False
        
        # 2. Process Edits
        for row_index, changes in editor_state.get("edited_rows", {}).items():
            user_id_to_update = original_df.iloc[row_index]['id']
            
            # Get the full state of the edited row from the `edited_df` variable
            full_edited_row = edited_df.iloc[row_index]
            
            approver_id = approver_name_to_id.get(full_edited_row['approver_name'])
            category_id = category_name_to_id.get(full_edited_row['default_category_name'])
            
            if not su.update_user_details(user_id_to_update, full_edited_row['role'], approver_id, category_id):
                all_success = False

        # 3. Process Additions
        for new_user_data in editor_state.get("added_rows", []):
            st.warning(f"A new row was added for user '{new_user_data.get('name')}' but cannot be saved without a password. Please use the 'Create a New User' form above.")
            all_success = False
        
        if all_success:
            st.success("All changes saved successfully!")
            # Reset the original dataframe state to the new state
            st.session_state.original_users_df = pd.DataFrame(edited_df)
            st.rerun()
        else:
            st.error("One or more changes could not be saved. Please review warnings and try again.")
