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
st.info("Edit user roles, approvers, and default categories below. Changes are saved automatically.")

all_users_df = su.get_all_users()
approvers = su.get_all_approvers()
categories = su.get_all_categories()

approver_dict = {approver['name']: approver['id'] for approver in approvers}
approver_names = ["None"] + list(approver_dict.keys())

category_dict = {cat['name']: cat['id'] for cat in categories}
category_names = ["None"] + list(category_dict.keys())


if all_users_df.empty:
    st.warning("No users found.")
    st.stop()

# Prepare dataframe for editing
id_to_name_map = {v: k for k, v in approver_dict.items()}
all_users_df['approver_name'] = all_users_df['approver_id'].map(id_to_name_map).fillna("None")
all_users_df['default_category_name'] = all_users_df['default_category_name'].fillna("None")


edited_df = st.data_editor(
    all_users_df,
    column_config={
        "id": None, "approver_id": None, "default_category_id": None,
        "role": st.column_config.SelectboxColumn("Role", options=["user", "approver", "admin"], required=True),
        "approver_name": st.column_config.SelectboxColumn("Approver", options=approver_names),
        "default_category_name": st.column_config.SelectboxColumn("Default Category", options=category_names)
    },
    disabled=["username", "name", "email"], # Make these fields read-only
    hide_index=True,
    key="user_editor"
)

# --- Save Changes to Database ---
# A button is no longer needed, data_editor saves changes on each edit.
# To make this robust, we find the row that changed.
if 'last_edited_df' not in st.session_state:
    st.session_state.last_edited_df = all_users_df

if not pd.DataFrame(edited_df).equals(st.session_state.last_edited_df):
    # Find the changed rows by comparing the data editor's state with the last known state
    comparison_df = st.session_state.last_edited_df.merge(edited_df, on='id', how='outer', indicator=True)
    changed_rows = comparison_df[comparison_df['_merge'] == 'right_only']

    if not changed_rows.empty:
        for index, row in changed_rows.iterrows():
            user_id = row['id']
            new_approver_id = approver_dict.get(row['approver_name_y'])
            new_category_id = category_dict.get(row['default_category_name_y'])
            
            su.update_user_details(
                user_id,
                row['role_y'],
                new_approver_id,
                new_category_id
            )
        st.success("User details updated!")
        # Update the session state and rerun
        st.session_state.last_edited_df = edited_df
        st.rerun()

# Update the baseline state after the initial draw
st.session_state.last_edited_df = edited_df
