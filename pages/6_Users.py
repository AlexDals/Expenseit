# File: pages/6_Users.py

import streamlit as st
from utils.supabase_utils import get_all_users
from utils.ui_utils import hide_streamlit_pages_nav
from utils.nav_utils import PAGES_FOR_ROLES

# *First thing* on the page:
hide_streamlit_pages_nav()  # :contentReference[oaicite:10]{index=10}

st.set_page_config(page_title="User Management", layout="wide")

# --- Sidebar Navigation (role-based) ---
role = st.session_state.get("role", "logged_out")
st.sidebar.header("Navigation")
for label, fname in PAGES_FOR_ROLES.get(role, PAGES_FOR_ROLES["logged_out"]):  # :contentReference[oaicite:11]{index=11}
    if fname in ("_7_Add_User.py", "_8_Edit_User.py"):
        continue
    if st.sidebar.button(label):
        st.switch_page(f"pages/{fname}")

# --- Authentication Guard ---
if not st.session_state.get("authentication_status"):
    st.warning("Please log in to access this page.")
    st.stop()

# --- Main User Management Content ---
if st.button("➕ Add User"):
    st.switch_page("pages/_7_Add_User.py")

users_df = get_all_users()
users = users_df.to_dict("records") if hasattr(users_df, "to_dict") else users_df

if not users:
    st.info("No users found.")
else:
    for u in users:
        c1, c2 = st.columns([4,1])
        if c1.button(f"✏️ {u['name']} (`{u['username']}`)", key=f"edit_{u['id']}"):
            st.session_state["selected_user_id"] = u["id"]
            st.switch_page("pages/_8_Edit_User.py")
        c2.markdown(f"**Role:** `{u.get('role', '')}`")  # :contentReference[oaicite:12]{index=12}
