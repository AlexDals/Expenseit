# File: pages/6_Users.py

import streamlit as st
from utils.supabase_utils import get_all_users

st.set_page_config(page_title="Users", layout="wide")
st.title("User Management")

# ➕ Add User button
if st.button("➕ Add User", use_container_width=True):
    st.switch_page("pages/7_Add_User.py")

# Ensure we have a slot for passing the selected user ID
st.session_state.setdefault("selected_user_id", None)

# Fetch all users
users_df = get_all_users()
users = users_df.to_dict("records") if hasattr(users_df, "to_dict") else users_df

if not users:
    st.info("No users found.")
else:
    for u in users:
        col1, col2 = st.columns([4, 1])
        # Edit button/navigation
        if col1.button(
            f"✏️ {u['name']} (`{u['username']}`)",
            key=f"edit_{u['id']}",
            use_container_width=True,
        ):
            st.session_state.selected_user_id = u["id"]
            st.switch_page("pages/8_Edit_User.py")
        col2.markdown(f"**Role:** `{u.get('role', '—')}`")
