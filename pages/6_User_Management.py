import streamlit as st
from utils import supabase_utils as su
import pandas as pd

st.title("⚙️ User Management")

if not st.session_state.get("authentication_status") or st.session_state.get("role") != 'admin':
    st.error("You do not have permission to access this page."); st.stop()

# --- Create User Form (unchanged) ---
with st.expander("➕ Create a New User"):
    # ... (form code is unchanged)

st.markdown("---")
st.subheader("Existing Users")
all_users_df = su.get_all_users()

if all_users_df.empty:
    st.warning("No users found.")
    st.stop()

# Display users in a more readable format
for index, user in all_users_df.iterrows():
    with st.container(border=True):
        col1, col2 = st.columns([4, 1])
        with col1:
            st.write(f"**{user['name']}** (`{user['username']}`)")
            st.caption(f"Role: `{user['role']}`")
        with col2:
            # --- FIX: Use st.page_link to navigate with a query parameter ---
            st.page_link(
                "pages/8_Edit_User.py", 
                label="Edit", 
                icon="✏️",
                use_container_width=True,
                query_params={"user_id": user['id']}
            )
