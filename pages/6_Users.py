import streamlit as st
from utils import supabase_utils as su
import pandas as pd

st.title("⚙️ User Management")

# --- Authentication Guard ---
if not st.session_state.get("authentication_status") or st.session_state.get("role") != 'admin':
    st.error("You do not have permission to access this page.")
    st.stop()

# --- Navigation ---
col1, col2 = st.columns([4, 1])
with col2:
    if st.button("➕ Add User", use_container_width=True, type="primary"):
        st.switch_page("pages/7_Add_User.py")

st.markdown("---")
st.subheader("Existing Users")
st.info("Click on a user's name to edit their details.")

all_users_df = su.get_all_users()

if all_users_df.empty:
    st.warning("No users found.")
    st.stop()

# --- Display User List ---
# We will use st.page_link which is the modern way to create navigation links
for index, user in all_users_df.iterrows():
    with st.container(border=True):
        col1, col2 = st.columns(2)
        # Create a clickable link on the user's name
        col1.page_link(
            f"pages/8_Edit_User.py?user_id={user['id']}", 
            label=f"**{user['name']}** (`{user['username']}`)",
            icon="✏️"
        )
        col2.write(f"**Role:** `{user['role']}`")
