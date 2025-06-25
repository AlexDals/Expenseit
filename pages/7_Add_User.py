# File: pages/7_Add_User.py

import streamlit as st
from utils.supabase_utils import (
    create_user_details,
    get_all_categories,
    get_all_approvers,
)

st.set_page_config(page_title="Add User", layout="centered")
st.title("Add User")

# — Basic user info
name = st.text_input("Name")
username = st.text_input("Username")
password = st.text_input("Password", type="password")

# — Role selector
roles = ["user", "admin", "approver"]
role = st.selectbox("Role", options=roles, index=0)

st.write("---")

# — Default Category selector
categories = get_all_categories()  # returns list of dicts: {'id', 'name', …}
cat_names = [c["name"] for c in categories]
selected_cat_name = st.selectbox("Default Category", options=cat_names)
selected_cat_id = next(c["id"] for c in categories if c["name"] == selected_cat_name)

# — Approver selector
approvers = get_all_approvers()  # returns list of dicts: {'id', 'name', …}
approver_names = [a["name"] for a in approvers]
selected_app_name = st.selectbox("Approver", options=approver_names)
selected_app_id = next(a["id"] for a in approvers if a["name"] == selected_app_name)

st.write("---")
# — Create button
if st.button("Create user"):
    # Basic validation
    if not name or not username or not password:
        st.error("Please fill out Name, Username, and Password.")
    else:
        success = create_user_details(
            name=name,
            username=username,
            password=password,
            role=role,
            approver_id=selected_app_id,
            default_category_id=selected_cat_id,
        )
        if success:
            st.success("User created successfully!")
            # Optionally reset fields or navigate back to Users page
            st.experimental_rerun()
        else:
            st.error("Failed to create user—please check the logs.")
