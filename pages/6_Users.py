# File: pages/6_Users.py

import streamlit as st
from utils.supabase_utils import get_all_users
from utils.ui_utils import hide_streamlit_pages_nav
from utils.nav_utils import PAGES_FOR_ROLES  # role-based pages mapping :contentReference[oaicite:2]{index=2}

# Page configuration
st.set_page_config(page_title="User Management", layout="wide")

# Hide default multipage nav and apply global CSS
hide_streamlit_pages_nav()

# --- Sidebar Navigation (role‐based) ---
role = st.session_state.get("role", "logged_out")
st.sidebar.header("Navigation")
for label, fname in PAGES_FOR_ROLES.get(role, PAGES_FOR_ROLES["logged_out"]):
    # Exclude the Add User and Edit User pages from the sidebar
    if fname in ("7_Add_User.py", "8_Edit_User.py"):
        continue
    # Exclude any hidden pages (prefixed with underscore)
    if fname.startswith("_"):
        continue
    if st.sidebar.button(label):
        st.switch_page(f"pages/{fname}")

# --- Authentication Guard ---
if not st.session_state.get("authentication_status"):
    st.warning("Please log in to access this page.")
    st.stop()

# --- Main User Management Content ---
st.title("User Management")

# In‐page button to add a new user
if st.button("➕ Add User"):
    st.switch_page("pages/7_Add_User.py")

# List existing users
users_df = get_all_users()
users    = users_df.to_dict("records") if hasattr(users_df, "to_dict") else users_df

if not users:
    st.info("No users found.")
else:
    for u in users:
        col_name, col_role = st.columns([4, 1])
        if col_name.button(f"✏️ {u['name']} (`{u['username']}`)", key=f"edit_{u['id']}"):
            st.session_state["selected_user_id"] = u["id"]
            st.switch_page("pages/8_Edit_User.py")
        col_role.markdown(f"**Role:** `{u.get('role', '')}`")
