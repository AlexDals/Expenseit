# File: pages/_7_Add_User.py

import streamlit as st
from utils.supabase_utils import init_connection, get_all_approvers, get_all_categories
from utils.ui_utils import hide_streamlit_pages_nav
from utils.nav_utils import PAGES_FOR_ROLES  # role‐based page definitions :contentReference[oaicite:4]{index=4}

# Page config
st.set_page_config(page_title="Add User", layout="wide")
# Hide Streamlit’s built-in nav & apply global CSS
hide_streamlit_pages_nav()  # :contentReference[oaicite:5]{index=5}

# --- Sidebar Navigation (role‐based) ---
role = st.session_state.get("role", "logged_out")
st.sidebar.header("Navigation")
for label, fname in PAGES_FOR_ROLES.get(role, PAGES_FOR_ROLES["logged_out"]):
    # Never show Add User or Edit User in the sidebar
    if fname in ("7_Add_User.py", "8_Edit_User.py"):
        continue
    if st.sidebar.button(label):
        st.switch_page(f"pages/{fname}")

st.title("Add User")

supabase  = init_connection()
approvers = get_all_approvers()
cats      = get_all_categories()

username = st.text_input("Username")
name     = st.text_input("Full Name")
email    = st.text_input("Email")
role_sel = st.selectbox("Role", ["user","approver","admin"])
approver = st.selectbox("Approver", [a["name"] for a in approvers])
category = st.selectbox("Default Category", [c["name"] for c in cats])
password = st.text_input("Password", type="password")

if st.button("Create User"):
    if not username or not password:
        st.error("Username and password required.")
    else:
        import bcrypt
        pwd_b = password.encode("utf-8")
        salt  = bcrypt.gensalt()
        hsh   = bcrypt.hashpw(pwd_b, salt).decode("utf-8")
        new_u = {
            "username": username,
            "name":     name,
            "email":    email,
            "role":     role_sel,
            "approver_id": next(a["id"] for a in approvers if a["name"] == approver),
            "default_category_id": next(c["id"] for c in cats if c["name"] == category),
            "password": hsh,
        }
        res = supabase.table("users").insert(new_u).execute()
        if getattr(res, "error", None):
            st.error(f"Error: {res.error.message}")
        else:
            st.success("User created.")
            st.experimental_rerun()
