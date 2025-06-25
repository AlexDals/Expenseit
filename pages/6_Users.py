# File: pages/6_Users.py

import streamlit as st
import pandas as pd
from utils.db_utils import get_all_users  # your function to fetch the users

# Optional: make sure session_state key exists
if "selected_user_id" not in st.session_state:
    st.session_state.selected_user_id = None

st.set_page_config(page_title="Users", layout="wide")
st.title("User Management")

# Load your users into a DataFrame or list of dicts
users = get_all_users()  # e.g. returns List[Dict] or pd.DataFrame
if isinstance(users, pd.DataFrame):
    all_users = users.to_dict(orient="records")
else:
    all_users = users

if not all_users:
    st.info("No users found.")
else:
    for user in all_users:
        col1, col2 = st.columns([4, 1])
        # Button sets session_state and switches pages
        if col1.button(
            f"✏️ {user['name']} (`{user['username']}`)",
            key=f"edit_{user['id']}",
            use_container_width=True,
        ):
            st.session_state.selected_user_id = user["id"]
            st.switch_page("pages/8_Edit_User.py")

        col2.markdown(f"**Role:** `{user.get('role','—')}`")
