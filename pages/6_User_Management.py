import streamlit as st
from utils import supabase_utils as su
import pandas as pd

st.title("⚙️ User Management")

if not st.session_state.get("authentication_status") or st.session_state.get("role") != 'admin':
    st.error("You do not have permission to access this page."); st.stop()

# Initialize session state to store the user ID to edit
if 'user_id_to_edit' not in st.session_state:
    st.session_state.user_id_to_edit = None

# Logic for the Edit buttons
def on_edit_click(user_id):
    st.session_state.user_id_to_edit = user_id
    st.switch_page("pages/8_Edit_User.py")

st.info("Select a user from the list below to edit their details.")
all_users_df = su.get_all_users()

if all_users_df.empty:
    st.warning("No users found.")
    st.stop()

# Display users in a more readable format
for index, user in all_users_df.iterrows():
    with st.container(border=True):
        col1, col2, col3 = st.columns([3, 2, 1])
        col1.write(f"**{user['name']}** (`{user['username']}`)")
        col2.write(f"Role: `{user['role']}`")
        col3.button("Edit", key=f"edit_{user['id']}", on_click=on_edit_click, args=(user['id'],), use_container_width=True)
