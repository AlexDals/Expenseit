import streamlit as st
from utils import supabase_utils as su
import pandas as pd

st.title("✏️ Edit User Profile")

# --- Authentication Guard ---
if not st.session_state.get("authentication_status") or st.session_state.get("role") != 'admin':
    st.error("You do not have permission to access this page."); st.stop()

# --- FIX: Get user ID from the URL query parameter ---
user_id_to_edit = st.query_params.get("user_id")

if not user_id_to_edit:
    st.error("No user selected for editing.")
    st.page_link("pages/6_User_Management.py", label="← Back to User Management", icon="⚙️")
    st.stop()

# --- Fetch Data for Dropdowns and User Details ---
user_data = su.get_single_user_details(user_id_to_edit)
if not user_data:
    st.error("Could not fetch details for the selected user."); st.stop()

approvers = su.get_all_approvers()
categories = su.get_all_categories()
approver_map = {approver['id']: approver['name'] for approver in approvers}
approver_options = [""] + list(approver_map.values())
approver_name_to_id = {v: k for k, v in approver_map.items()}
category_map = {cat['id']: cat['name'] for cat in categories}
category_options = [""] + list(category_map.values())
category_name_to_id = {v: k for k, v in category_map.items()}

# --- Edit Form ---
with st.form("edit_user_form"):
    st.subheader(f"Editing profile for: {user_data['name']} (`{user_data['username']}`)")
    st.write(f"Email: {user_data['email']}")
    st.markdown("---")

    current_role_index = ["user", "approver", "admin"].index(user_data.get('role', 'user'))
    current_approver_name = approver_map.get(user_data.get('approver_id'), "")
    current_approver_index = approver_options.index(current_approver_name) if current_approver_name in approver_options else 0
    current_category_name = category_map.get(user_data.get('default_category_id'), "")
    current_category_index = category_options.index(current_category_name) if current_category_name in category_options else 0

    new_role = st.selectbox("Role", options=["user", "approver", "admin"], index=current_role_index)
    new_approver_name = st.selectbox("Approver", options=approver_options, index=current_approver_index)
    new_category_name = st.selectbox("Default Category", options=category_options, index=current_category_index)
    
    submitted = st.form_submit_button("Save Changes")
    if submitted:
        approver_id = approver_name_to_id.get(new_approver_name)
        category_id = category_name_to_id.get(new_category_name)
        
        with st.spinner("Saving..."):
            if su.update_user_details(user_id_to_edit, new_role, approver_id, category_id):
                st.success("User details updated successfully!")
                st.info("Returning to user list...")
                # Clear the query param and switch page
                st.query_params.clear()
                st.switch_page("pages/6_User_Management.py")
            else:
                st.error("Failed to update user details.")

st.page_link("pages/6_User_Management.py", label="← Back to User Management", icon="⚙️")
