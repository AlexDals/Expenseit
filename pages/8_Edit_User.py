# File: pages/_8_Edit_User.py

import streamlit as st
from utils.supabase_utils import (
    init_connection,
    get_single_user_details,
    get_all_categories,
    get_all_approvers,
)
from utils.ui_utils import hide_streamlit_pages_nav
from utils.nav_utils import PAGES_FOR_ROLES  # role‐based page definitions :contentReference[oaicite:7]{index=7}

# Page config
st.set_page_config(page_title="Edit User", layout="wide")
# Hide Streamlit’s built-in nav & apply global CSS
hide_streamlit_pages_nav()  # :contentReference[oaicite:8]{index=8}

# --- Sidebar Navigation (role‐based) ---
role = st.session_state.get("role", "logged_out")
st.sidebar.header("Navigation")
for label, fname in PAGES_FOR_ROLES.get(role, PAGES_FOR_ROLES["logged_out"]):
    # Never show Add User or Edit User in the sidebar
    if fname in ("7_Add_User.py", "8_Edit_User.py"):
        continue
    if st.sidebar.button(label):
        st.switch_page(f"pages/{fname}")

st.title("Edit User")

supabase   = init_connection()
uid        = st.session_state.get("selected_user_id")
if not uid:
    st.error("No user selected.")
    st.stop()

details    = get_single_user_details(uid)
approvers  = get_all_approvers()
categories = get_all_categories()

# Build dropdown options with “(None)” entries
approver_names = ["(None)"] + [a["name"] for a in approvers]
approver_ids   = [None]    + [a["id"]   for a in approvers]
cat_names      = [c["name"] for c in categories]
cat_ids        = [c["id"]   for c in categories]

# Compute safe indices
current_app = details.get("approver_id")
app_index   = approver_ids.index(current_app) if current_app in approver_ids else 0
current_cat = details.get("default_category_id")
cat_index   = cat_ids.index(current_cat) if current_cat in cat_ids else 0

name     = st.text_input("Full Name", value=details.get("name", ""))
email    = st.text_input("Email",     value=details.get("email", ""))

role_sel = st.selectbox(
    "Role",
    ["user", "approver", "admin"],
    index=["user", "approver", "admin"].index(details.get("role", "user"))
)

approver = st.selectbox(
    "Approver",
    options=approver_names,
    index=app_index
)

category = st.selectbox(
    "Default Category",
    options=cat_names,
    index=cat_index
)

department = st.selectbox(
    "Department",
    options=["(None)"] + [d["name"] for d in supabase.table("departments").select("name,id").execute().data],
    index=0  # default to “(None)”; adjust similarly if persisting
)

if st.button("Save changes"):
    selected_approver_id   = approver_ids[approver_names.index(approver)]
    selected_category_id   = cat_ids[cat_names.index(category)]
    # department_id mapping omitted here if not managed via supabase_utils
    try:
        update = {
            "role":                role_sel,
            "approver_id":         selected_approver_id,
            "default_category_id": selected_category_id,
        }
        # Include department_id if desired:
        # update["department_id"] = selected_department_id
        supabase.table("users").update(update).eq("id", uid).execute()
        st.success("User updated successfully.")
    except Exception as e:
        st.error(f"Error updating user: {e}")
