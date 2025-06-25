# File: pages/6_Users.py

import streamlit as st
import pandas as pd
from utils.supabase_utils import get_all_users

st.set_page_config(page_title="Users", layout="wide")
st.title("User Management")

# Ensure we have a slot for the selected user
st.session_state.setdefault("selected_user_id", None)

# Fetch all users as a DataFrame
users_df: pd.DataFrame = get_all_users()

if users_df.empty:
    st.info("No users found.")
else:
    users = users_df.to_dict(orient="records")
    for u in users:
        col1, col2 = st.columns([4, 1])
        # Clicking this button stores the ID and jumps to the edit page
        if col1.button(
            f"✏️ {u['name']} (`{u['username']}`)",
            key=f"edit_{u['id']}",
            use_container_width=True,
        ):
            st.session_state.selected_user_id = u["id"]
            st.switch_page("pages/8_Edit_User.py")
        col2.markdown(f"**Role:** `{u.get('role','—')}`")
