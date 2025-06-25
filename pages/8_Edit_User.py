# File: pages/8_Edit_User.py

import streamlit as st
from utils.db_utils import get_user_by_id, update_user  # your fetch/update functions

st.set_page_config(page_title="Edit User", layout="centered")
st.title("Edit User")

# Retrieve the ID that we stored in session_state
user_id = st.session_state.get("selected_user_id")
if user_id is None:
    st.error("No user was selected. Please go back and choose a user to edit.")
    st.stop()

# Fetch existing user data
user = get_user_by_id(user_id)
if user is None:
    st.error(f"User with ID {user_id} not found.")
    st.stop()

# Editable fields
name = st.text_input("Name", value=user["name"])
username = st.text_input("Username", value=user["username"])
role = st.selectbox(
    "Role",
    options=["Admin", "Editor", "Viewer"],  # replace with your actual roles
    index=["Admin", "Editor", "Viewer"].index(user.get("role", "Viewer")),
)

st.write("---")
if st.button("Save changes"):
    success = update_user(user_id, name=name, username=username, role=role)
    if success:
        st.success("User updated successfully!")
    else:
        st.error("Failed to update user—check the logs.")
