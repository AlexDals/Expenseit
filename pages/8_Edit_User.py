# File: pages/8_Edit_User.py

import os
import sys

# ─ Ensure project root is on Python path ────────────────
_this_dir = os.path.dirname(__file__)
_project_root = os.path.abspath(os.path.join(_this_dir, ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import streamlit as st
from utils.db_utils import get_user_by_id, update_user  # now resolvable

st.set_page_config(page_title="Edit User", layout="centered")
st.title("Edit User")

# Pull the user_id we stored
user_id = st.session_state.get("selected_user_id")
if user_id is None:
    st.error("No user was selected. Please go back and choose one.")
    st.stop()

# Load user record
user = get_user_by_id(user_id)
if user is None:
    st.error(f"User with ID {user_id} not found.")
    st.stop()

# Edit fields
name = st.text_input("Name", value=user["name"])
username = st.text_input("Username", value=user["username"])
roles = ["Admin", "Editor", "Viewer"]  # adjust as needed
st.session_state.setdefault("role_index", roles.index(user.get("role", roles[0])))
role = st.selectbox("Role", options=roles, index=st.session_state.role_index)

st.write("---")
if st.button("Save changes"):
    ok = update_user(user_id, name=name, username=username, role=role)
    if ok:
        st.success("User updated successfully!")
    else:
        st.error("Failed to update user—check the logs.")
