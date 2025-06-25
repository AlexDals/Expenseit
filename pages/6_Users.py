# File: pages/6_Users.py

import os
import sys

# ─ Ensure project root is on Python path ────────────────
_this_dir = os.path.dirname(__file__)
_project_root = os.path.abspath(os.path.join(_this_dir, ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import streamlit as st
from utils.db_utils import get_all_users  # now resolvable

# Initialize session_state key if missing
st.session_state.setdefault("selected_user_id", None)

st.set_page_config(page_title="Users", layout="wide")
st.title("User Management")

# Fetch users
all_users = get_all_users()  # should return list[dict] or DataFrame
if hasattr(all_users, "to_dict"):
    all_users = all_users.to_dict(orient="records")

if not all_users:
    st.info("No users found.")
else:
    for user in all_users:
        col1, col2 = st.columns([4, 1])
        if col1.button(
            f"✏️ {user['name']} (`{user['username']}`)",
            key=f"edit_{user['id']}",
            use_container_width=True,
        ):
            st.session_state.selected_user_id = user["id"]
            st.switch_page("pages/8_Edit_User.py")

        col2.markdown(f"**Role:** `{user.get('role','—')}`")
