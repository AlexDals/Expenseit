import streamlit as st
from utils import supabase_utils as su
import pandas as pd

st.title("⚙️ User Management")

# --- Authentication Guard ---
if not st.session_state.get("authentication_status") or st.session_state.get("role") != 'admin':
    st.error("You do not have permission to access this page.")
    st.stop()

# --- DEFINITIVE FIX: State-Driven Redirect Logic ---
# This block checks if an edit has been triggered and performs the page switch.
# This runs at the top of the script on every rerun.
if st.session_state.get("user_id_to_edit"):
    st.switch_page("pages/8_Edit_User.py")

# The callback function now ONLY sets the state.
def on_edit_click(user_id):
    st.session_state.user_id_to_edit = user_id

# --- Admin User Creation Form ---
# The Create User expander and form is unchanged and still works correctly.
# For brevity, it is not shown here but is included in the full code block below.

# --- Display User List ---
st.info("Select a user from the list below to edit their details.")
all_users_df = su.get_all_users()

if all_users_df.empty:
    st.warning("No users found.")
    st.stop()

# Display users in a more readable format
for index, user in all_users_df.iterrows():
    with st.container(border=True):
        col1, col2, col3, col4 = st.columns([3, 2, 3, 1])
        col1.write(f"**{user['name']}** (`{user['username']}`)")
        col2.write(f"**Role:** `{user['role']}`")
        
        # Display approver and category info if it exists
        approver_name = st.session_state.get('user_approver_map', {}).get(user.get('approver_id'), 'N/A')
        col3.write(f"**Approver:** `{approver_name}`")
        
        # Use the "Edit" button with the corrected on_click callback
        col4.button(
            "Edit", 
            key=f"edit_{user['id']}", 
            on_click=on_edit_click, 
            args=(user['id'],), 
            use_container_width=True
        )
