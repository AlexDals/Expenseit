import streamlit as st
from utils import supabase_utils as su
import pandas as pd

st.set_page_config(layout="wide")
st.title("⚙️ User Management")

# --- Authentication and Role Check ---
# Ensure user is logged in and is an admin
if 'authentication_status' not in st.session_state or not st.session_state['authentication_status']:
    st.warning("Please log in to access this page.")
    st.stop()
elif st.session_state.get("role") != 'admin':
    st.error("You do not have permission to access this page.")
    st.stop()

# --- Fetch Data ---
all_users_df = su.get_all_users()
approvers = su.get_all_approvers()
approver_dict = {approver['name']: approver['id'] for approver in approvers}
approver_names = ["None"] + list(approver_dict.keys())

if all_users_df.empty:
    st.warning("No users found.")
    st.stop()

# Create a mapping from approver_id to approver_name for display
id_to_name_map = {v: k for k, v in approver_dict.items()}
all_users_df['approver_name'] = all_users_df['approver_id'].map(id_to_name_map).fillna("None")

# --- Display and Edit User Data ---
st.info("Edit user roles and assign approvers below. Changes are saved automatically.")

# Use st.data_editor to make the table interactive
edited_df = st.data_editor(
    all_users_df,
    column_config={
        "id": None, # Hide the ID column
        "approver_id": None, # Hide the approver_id column
        "role": st.column_config.SelectboxColumn(
            "Role",
            help="The user's role in the app",
            options=["user", "approver", "admin"],
            required=True,
        ),
        "approver_name": st.column_config.SelectboxColumn(
            "Approver",
            help="The user who approves this user's reports",
            options=approver_names,
            required=True,
        ),
    },
    hide_index=True,
    key="user_editor"
)

# --- Save Changes to Database ---
# Compare the original and edited dataframes to find what changed
if edited_df is not None and not all_users_df.equals(edited_df):
    # Find the changed rows
    diff = all_users_df.merge(edited_df, indicator=True, how='outer').loc[lambda x : x['_merge']=='right_only']
    
    for index, row in diff.iterrows():
        user_id = row['id']
        new_role = row['role']
        new_approver_name = row['approver_name']
        new_approver_id = approver_dict.get(new_approver_name, None) # Convert name back to ID
        
        # Call Supabase update function
        su.update_user_details(user_id, new_role, new_approver_id)
    
    st.success("User details updated!")
    st.rerun() # Rerun to reflect changes immediately
