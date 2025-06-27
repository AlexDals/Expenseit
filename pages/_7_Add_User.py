# File: pages/7_Add_User.py

import streamlit as st
import bcrypt
from utils.supabase_utils import init_connection, get_all_approvers
from utils.ui_utils import hide_streamlit_pages_nav

# *First thing* on the page:
hide_streamlit_pages_nav()

st.set_page_config(page_title="Login", layout="wide")

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

# — Supabase client
supabase = init_connection()

# — Default Category selector
#   Fetch all categories from Supabase
categories = supabase.table("categories").select("id, name").execute().data or []
if not categories:
    st.error("No categories found. Please add some first.")
    st.stop()

cat_names = [c["name"] for c in categories]
selected_cat_name = st.selectbox("Default Category", options=cat_names)
selected_cat_id = next(c["id"] for c in categories if c["name"] == selected_cat_name)

# — Approver selector
approvers = get_all_approvers()  # list of dicts: {'id', 'name'}
if not approvers:
    st.error("No approvers found. Please ensure you have at least one approver user.")
    st.stop()

approver_names = [a["name"] for a in approvers]
selected_app_name = st.selectbox("Approver", options=approver_names)
selected_app_id = next(a["id"] for a in approvers if a["name"] == selected_app_name)

st.write("---")
if st.button("Create user"):
    # Basic validation
    if not (name and username and password):
        st.error("Please fill out Name, Username, and Password.")
    else:
        # Hash the password
        hashed_pw = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode()

        # Prepare the new user record
        new_user = {
            "name": name,
            "username": username,
            "hashed_password": hashed_pw,
            "role": role,
            "approver_id": selected_app_id,
            "default_category_id": selected_cat_id,
        }

        # Insert into Supabase
        try:
            result = supabase.table("users").insert(new_user).execute()
            if result.error:
                st.error(f"Error creating user: {result.error.message}")
            else:
                st.success("User created successfully!")
                # Reset the form or redirect back to Users page
                st.experimental_rerun()
        except Exception as e:
            st.error(f"Unexpected error: {e}")
