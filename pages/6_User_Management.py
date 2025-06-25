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
    # ... (This form code remains unchanged) ...
    
st.markdown("---")

# --- Existing User Editing Logic ---
st.subheader("Edit Existing Users")
st.info("You can edit user roles, approvers, and default categories below.")

# --- Data Preparation for Editor ---
try:
    all_users_df = su.get_all_users()
    approvers = su.get_all_approvers()
    categories = su.get_all_categories()

    approver_map = {approver['id']: approver['name'] for approver in approvers}
    approver_options = [""] + list(approver_map.values())
    approver_name_to_id = {v: k for k, v in approver_map.items()}

    category_map = {cat['id']: cat['name'] for cat in categories}
    category_options = [""] + list(category_map.values())
    category_name_to_id = {v: k for k, v in category_map.items()}
    
    if not all_users_df.empty:
        # Prepare dataframe for editing by replacing IDs with human-readable names
        all_users_df['approver_name'] = all_users_df['approver_id'].map(approver_map).fillna("")
        all_users_df['default_category_name'] = all_users_df['default_category_id'].map(category_map).fillna("")
    
except Exception as e:
    st.error(f"An error occurred preparing user data: {e}")
    all_users_df = pd.DataFrame()


if all_users_df.empty:
    st.warning("No users found or an error occurred.")
    st.stop()

# --- The Data Editor ---
edited_df = st.data_editor(
    all_users_df,
    column_config={
        "id": None, "approver_id": None, "default_category_id": None, 
        "username": "Username", "name": "Full Name", "email": "Email",
        "role": st.column_config.SelectboxColumn("Role", options=["user", "approver", "admin"], required=True),
        "approver_name": st.column_config.SelectboxColumn("Approver", options=approver_options),
        "default_category_name": st.column_config.SelectboxColumn("Default Category", options=category_options)
    },
    disabled=["username", "name", "email"],
    hide_index=True,
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
            
            # This handles any new rows added in the UI that won't have an ID
            if pd.isna(user_id):
                st.warning(f"Skipping newly added row for '{user_data.get('name')}'. Please use the 'Create a New User' form.")
                continue

            # Convert friendly names back to IDs for saving
            approver_id = approver_name_to_id.get(user_data['approver_name'])
            category_id = category_name_to_id.get(user_data['default_category_name'])
            
            # Call the update details function for every existing user
            # A more advanced version would compare to see if the row changed, but this is more robust
            if not su.update_user_details(user_id, user_data['role'], approver_id, category_id):
                all_success = False
        
        if all_success:
            st.success("All changes saved successfully!")
            st.rerun()
        else:
            st.error("One or more changes could not be saved.")
