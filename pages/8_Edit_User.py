import streamlit as st
from utils.nav_utils import filter_pages_by_role
filter_pages_by_role()

from utils.supabase_utils import (
    init_connection,
    get_single_user_details,
    update_user_details,
    get_all_categories,
    get_all_approvers,
)

st.set_page_config(layout="wide", page_title="Edit User")
st.title("Edit User")

supabase = init_connection()
uid       = st.session_state.get("selected_user_id")
if not uid:
    st.error("No user selected.")
    st.stop()

details   = get_single_user_details(uid)
approvers = get_all_approvers()
cats      = get_all_categories()

name     = st.text_input("Full Name", value=details.get("name",""))
email    = st.text_input("Email", value=details.get("email",""))
role     = st.selectbox("Role", ["user","approver","admin"], index=["user","approver","admin"].index(details.get("role","user")))
approver = st.selectbox("Approver", [a["name"] for a in approvers], index=[a["id"] for a in approvers].index(details.get("approver_id")))
category = st.selectbox("Default Category", [c["name"] for c in cats], index=[c["id"] for c in cats].index(details.get("default_category_id")))

if st.button("Save changes"):
    success = update_user_details(
        uid,
        role=role,
        approver_id=approvers[approver]["id"],
        default_category_id=cats[category]["id"]
    )
    if success:
        st.success("User updated.")
    else:
        st.error("Update failed.")
