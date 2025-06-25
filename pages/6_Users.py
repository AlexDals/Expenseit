# File: pages/6_Users.py

import streamlit as st
from utils.db_utils import get_all_users

st.set_page_config(page_title="Users", layout="wide")
st.title("User Management")

# Ensure the session key exists
st.session_state.setdefault("selected_user_id", None)

# Fetch users (list of dicts or a DataFrame)
users = get_all_users()
if hasattr(users, "to_dict"):
    users = users.to_dict(orient="records")

if not users:
    st.info("No users found.")
else:
    for u in users:
        col1, col2 = st.columns([4, 1])
        if col1.button(
            f"✏️ {u['name']} (`{u['username']}`)",
            key=f"edit_{u['id']}",
            use_container_width=True,
        ):
            st.session_state.selected_user_id = u["id"]
            st.switch_page("pages/8_Edit_User.py")
        col2.markdown(f"**Role:** `{u.get('role','—')}`")
