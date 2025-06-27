# File: pages/6_Users.py

import streamlit as st
from utils.supabase_utils import get_all_users
from utils.ui_utils import hide_streamlit_pages_nav

# *First thing* on the page:
hide_streamlit_pages_nav()

st.set_page_config(page_title="User Management", layout="wide")
st.title("User Management")

if not st.session_state.get("authentication_status"):
    st.warning("Please log in to access this page.")
    st.stop()

if st.button("➕ Add User"):
    st.switch_page("pages/7_Add_User.py")

users_df = get_all_users()
users = users_df.to_dict("records") if hasattr(users_df, "to_dict") else users_df

if not users:
    st.info("No users found.")
else:
    for u in users:
        c1, c2 = st.columns([4, 1])
        if c1.button(f"✏️ {u['name']} (`{u['username']}`)", key=f"edit_{u['id']}"):
            st.session_state["selected_user_id"] = u["id"]
            st.switch_page("pages/8_Edit_User.py")
        c2.markdown(f"**Role:** `{u.get('role', '')}`")
