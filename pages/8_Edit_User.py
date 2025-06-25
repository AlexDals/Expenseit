# File: pages/8_Edit_User.py

import streamlit as st
from utils.supabase_utils import get_single_user_details, update_user_details

st.set_page_config(page_title="Edit User", layout="centered")
st.title("Edit User")

# Retrieve the ID we stashed in session_state
user_id = st.session_state.get("selected_user_id")
if not user_id:
    st.error("No user selected. Please go back and choose a user.")
    st.stop()

# Load the user’s current details
user = get_single_user_details(user_id)
if not user:
    st.error(f"User with ID {user_id} not found.")
    st.stop()

# Build the edit form
name = st.text_input("Name", value=user["name"])
username = st.text_input("Username", value=user["username"])

# Role choices (adjust to match your actual roles)
roles = ["user", "admin", "approver"]
current_role = user.get("role", roles[0])
role = st.selectbox("Role", options=roles, index=roles.index(current_role))

# (Optional) If you expose approver or default category edits, add more fields here…

st.write("---")
if st.button("Save changes"):
    success = update_user_details(
        user_id,
        role=role,
        approver_id=user.get("approver_id"),
        default_category_id=user.get("default_category_id"),
    )
    if success:
        st.success("User updated successfully!")
    else:
        st.error("Failed to update user—check the logs.")
