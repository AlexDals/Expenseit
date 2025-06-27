import streamlit as st
from utils.nav_utils import filter_pages_by_role
filter_pages_by_role()

from utils.supabase_utils import get_all_users

st.set_page_config(layout="wide", page_title="User Management")
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
        c1, c2 = st.columns([4,1])
        if c1.button(f"✏️ {u['name']} (`{u['username']}`)", key=u["id"]):
            st.session_state["selected_user_id"] = u["id"]
            st.switch_page("pages/8_Edit_User.py")
        c2.markdown(f"**Role:** `{u.get('role','')}`")
