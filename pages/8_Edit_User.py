# File: pages/8_Edit_User.py

import streamlit as st
from utils.db_utils import get_user_by_id, update_user

st.set_page_config(page_title="Edit User", layout="centered")
st.title("Edit User")

# Grab the ID we stored
user_id = st.session_state.get("selected_user_id")
if not user_id:
    st.error("No user was selected. Go back and pick one.")
    st.stop()

# Load and validate
user = get_user_by_id(user_id)
if not user:
    st.error(f"User with ID {user_id} not found.")
    st.stop()

# Editable form
name = st.text_input("Name", value=user["name"])
username = st.text_input("Username", value=user["username"])
roles = ["Admin", "Editor", "Viewer"]  # adapt to your schema
current = user.get("role", roles[0])
role = st.selectbox("Role", options=roles, index=roles.index(current))

st.write("---")
if st.button("Save changes"):
    ok = update_user(user_id, name=name, username=username, role=role)
    if ok:
        st.success("User updated successfully!")
    else:
        st.error("Failed to update user. Check your logs.")
