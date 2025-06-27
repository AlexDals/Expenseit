# File: pages/_8_Edit_User.py

import streamlit as st
from utils.supabase_utils import (
    init_connection,
    get_single_user_details,
    update_user_details,
    get_all_categories,
    get_all_approvers,
)
from utils.ui_utils import hide_streamlit_pages_nav

# *First thing* on the page:
hide_streamlit_pages_nav()

st.set_page_config(page_title="Edit User", layout="wide")
st.title("Edit User")

supabase = init_connection()
uid = st.session_state.get("selected_user_id")
if not uid:
    st.error("No user selected.")
    st.stop()

details   = get_single_user_details(uid)
approvers = get_all_approvers()
cats      = get_all_categories()

# —————————————————————————————————————————————————————————————————————————
# Build safe approver lists with a “None” option
approver_names = ["(None)"] + [a["name"] for a in approvers]
approver_ids   = [None]    + [a["id"]   for a in approvers]
# Compute a safe default index
current_approver = details.get("approver_id")
if current_approver in approver_ids:
    approver_index = approver_ids.index(current_approver)
else:
    approver_index = 0
# —————————————————————————————————————————————————————————————————————————

name     = st.text_input("Full Name", value=details.get("name", ""))
email    = st.text_input("Email",     value=details.get("email", ""))
role     = st.selectbox(
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
    [c["name"] for c in cats],
    index=[c["id"] for c in cats].index(details.get("default_category_id")) 
             if details.get("default_category_id") in [c["id"] for c in cats] 
             else 0
)

if st.button("Save changes"):
    # Map back from name to ID (None remains None)
    selected_approver_id = approver_ids[approver_names.index(approver)]
    selected_category_id = next(
        (c["id"] for c in cats if c["name"] == category), 
        None
    )

    success = update_user_details(
        uid,
        role=role,
        approver_id=selected_approver_id,
        default_category_id=selected_category_id,
    )
    if success:
        st.success("User updated.")
    else:
        st.error("Update failed.")
