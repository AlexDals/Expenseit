# File: pages/8_Edit_User.py

import streamlit as st
from utils.supabase_utils import (
    get_single_user_details,
    update_user_details,
    get_all_categories,
    get_all_approvers,
)

st.set_page_config(page_title="Edit User", layout="centered")
st.title("Edit User")

# Retrieve the ID we stashed in session_state
user_id = st.session_state.get("selected_user_id")
if not user_id:
    st.error("No user selected. Please go back and choose a user.")
    st.stop()

# Load current user details
user = get_single_user_details(user_id)
if not user:
    st.error(f"User with ID {user_id} not found.")
    st.stop()

# Context info
st.markdown(f"**Name:** {user.get('name')}")
st.markdown(f"**Username:** `{user.get('username')}`")
st.write("---")

# — Role selector
roles = ["user", "admin", "approver"]
current_role = user.get("role", roles[0])
role = st.selectbox("Role", options=roles, index=roles.index(current_role))

# — Default Category selector
categories = get_all_categories()  # list of dicts with 'id','name'
cat_names = [c["name"] for c in categories]
curr_cat_id = user.get("default_category_id")
default_idx = next((i for i, c in enumerate(categories) if c["id"] == curr_cat_id), 0)
selected_cat_name = st.selectbox(
    "Default Category", options=cat_names, index=default_idx
)
selected_cat_id = next(c["id"] for c in categories if c["name"] == selected_cat_name)

# — Approver selector
approvers = get_all_approvers()  # list of dicts with 'id','name'
app_names = [a["name"] for a in approvers]
curr_app_id = user.get("approver_id")
approver_idx = next((i for i, a in enumerate(approvers) if a["id"] == curr_app_id), 0)
selected_app_name = st.selectbox(
    "Approver", options=app_names, index=approver_idx
)
selected_app_id = next(a["id"] for a in approvers if a["name"] == selected_app_name)

st.write("---")
if st.button("Save changes", use_container_width=True):
    success = update_user_details(
        user_id,
        role=role,
        approver_id=selected_app_id,
        default_category_id=selected_cat_id,
    )
    if success:
        st.success("User updated successfully!")
    else:
        st.error("Failed to update user—check the logs.")
