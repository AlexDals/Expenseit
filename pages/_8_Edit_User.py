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
uid       = st.session_state.get("selected_user_id")
if not uid:
    st.error("No user selected.")
    st.stop()

details   = get_single_user_details(uid)
approvers = get_all_approvers()
cats      = get_all_categories()

name     = st.text_input("Full Name", value=details.get("name", ""))
email    = st.text_input("Email", value=details.get("email", ""))
role     = st.selectbox("Role", ["user","approver","admin"], index=["user","approver","admin"].index(details.get("role","user")))
approver = st.selectbox("Approver", [a["name"] for a in approvers], index=[a["id"] for a in approvers].index(details.get("approver_id")))
category = st.selectbox("Default Category", [c["name"] for c in cats], index=[c["id"] for c in cats].index(details.get("default_category_id")))

if st.button("Save changes"):
    success = update_user_details(
        uid,
        role=role,
        approver_id=next(a["id"] for a in approvers if a["name"] == approver),
        default_category_id=next(c["id"] for c in cats if c["name"] == category),
    )
    if success:
        st.success("User updated.")
    else:
        st.error("Update failed.")
