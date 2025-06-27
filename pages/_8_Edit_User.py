# File: pages/_8_Edit_User.py

import streamlit as st
from utils.supabase_utils import (
    init_connection,
    get_single_user_details,
    get_all_categories,
    get_all_approvers,
)
from utils.ui_utils import hide_streamlit_pages_nav

# Hide built-in nav and apply global CSS
hide_streamlit_pages_nav()

st.set_page_config(page_title="Edit User", layout="wide")
st.title("Edit User")

# Initialize client and load user details
supabase = init_connection()
uid = st.session_state.get("selected_user_id")
if not uid:
    st.error("No user selected.")
    st.stop()

details   = get_single_user_details(uid)
approvers = get_all_approvers()
categories = get_all_categories()

# Fetch departments for the selectbox
try:
    deps = (
        supabase
        .table("departments")
        .select("id, name")
        .order("name", desc=False)
        .execute()
        .data
    ) or []
except Exception:
    deps = []

# — Build parallel lists for Approver dropdown (with “(None)” option) —
approver_names = ["(None)"] + [a["name"] for a in approvers]
approver_ids   = [None]    + [a["id"]   for a in approvers]
current_approver = details.get("approver_id")
approver_index = approver_ids.index(current_approver) if current_approver in approver_ids else 0

# — Build parallel lists for Category dropdown —
cat_names = [c["name"] for c in categories]
cat_ids   = [c["id"]   for c in categories]
current_cat = details.get("default_category_id")
cat_index = cat_ids.index(current_cat) if current_cat in cat_ids else 0

# — Build parallel lists for Department dropdown (with “(None)” option) —
dept_names = ["(None)"] + [d["name"] for d in deps]
dept_ids   = [None]     + [d["id"]   for d in deps]
current_dept = details.get("department_id")
dept_index = dept_ids.index(current_dept) if current_dept in dept_ids else 0

# — Form fields —
name     = st.text_input("Full Name", value=details.get("name", ""))
email    = st.text_input("Email",     value=details.get("email", ""))

role = st.selectbox(
    "Role",
    ["user", "approver", "admin"],
    index=["user", "approver", "admin"].index(details.get("role", "user"))
)

approver = st.selectbox(
    "Approver",
    options=approver_names,
    index=approver_index
)

category = st.selectbox(
    "Default Category",
    options=cat_names,
    index=cat_index
)

department = st.selectbox(
    "Department",
    options=dept_names,
    index=dept_index
)

# — Save changes —
if st.button("Save changes"):
    # Map back to IDs
    selected_approver_id  = approver_ids[approver_names.index(approver)]
    selected_category_id  = cat_ids[cat_names.index(category)]
    selected_department_id = dept_ids[dept_names.index(department)]

    updates = {
        "role":                  role,
        "approver_id":           selected_approver_id,
        "default_category_id":   selected_category_id,
        "department_id":         selected_department_id,
    }

    try:
        supabase.table("users").update(updates).eq("id", uid).execute()
        st.success("User updated successfully.")
    except Exception as e:
        st.error(f"Error updating user: {e}")
