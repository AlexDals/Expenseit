# File: pages/9_Category_Management.py

import streamlit as st
from utils.supabase_utils import (
    init_connection,
    get_all_users,
    get_single_user_details,
    update_user_details,
)

st.set_page_config(page_title="Category Management", layout="wide")
st.title("Category Management")

supabase = init_connection()

# --- 1) CATEGORY CRUD ---------------------------------------
st.header("Manage Categories")

# Load categories (including gl_account) and sort locally
try:
    res = supabase.table("categories").select("id, name, gl_account").execute()
    categories = res.data or []
    categories.sort(key=lambda c: c["name"].lower())
except Exception as e:
    st.error(f"Could not load categories: {e}")
    st.stop()

# Display existing categories with inline edit/delete
for cat in categories:
    col1, col2, col3, col4 = st.columns([3, 3, 1, 1])
    new_name = col1.text_input("", value=cat["name"], key=f"cat_name_{cat['id']}")
    new_gl = col2.text_input(
        "GL Account Number", value=cat.get("gl_account", ""), key=f"cat_gl_{cat['id']}"
    )
    if col3.button("Update", key=f"update_cat_{cat['id']}"):
        try:
            supabase.table("categories")\
                .update({"name": new_name, "gl_account": new_gl})\
                .eq("id", cat["id"])\
                .execute()
            st.success(f"Category '{new_name}' updated.")
            st.experimental_rerun()
        except Exception as e:
            st.error(f"Error updating category: {e}")
    if col4.button("Delete", key=f"delete_cat_{cat['id']}"):
        try:
            supabase.table("categories")\
                .delete()\
                .eq("id", cat["id"])\
                .execute()
            st.success(f"Deleted category '{cat['name']}'.")
            st.experimental_rerun()
        except Exception as e:
            st.error(f"Error deleting category: {e}")

# Add new category
st.subheader("Add New Category")
new_cat_name = st.text_input("Name", key="new_cat_name")
new_cat_gl = st.text_input("GL Account Number", key="new_cat_gl")
if st.button("Add Category"):
    if not new_cat_name:
        st.error("Please enter a category name.")
    else:
        try:
            supabase.table("categories")\
                .insert({"name": new_cat_name, "gl_account": new_cat_gl})\
                .execute()
            st.success(f"Added new category '{new_cat_name}'.")
            st.experimental_rerun()
        except Exception as e:
            st.error(f"Error adding category: {e}")

st.write("---")

# --- 2) ASSIGN DEFAULT CATEGORY TO USER --------------------
st.header("Assign Default Category to User")

# Fetch all users
users_df = get_all_users()
users = users_df.to_dict("records") if hasattr(users_df, "to_dict") else users_df

if not users:
    st.info("No users available for assignment.")
else:
    user_labels = [f"{u['name']} ({u['username']})" for u in users]
    sel_user_label = st.selectbox("Select User", user_labels, key="assign_user")
    sel_user = users[user_labels.index(sel_user_label)]

    cat_labels = [c["name"] for c in categories]
    sel_cat_name = st.selectbox("Select Default Category", cat_labels, key="assign_cat")
    sel_cat_id = next(c["id"] for c in categories if c["name"] == sel_cat_name)

    if st.button("Assign Default Category"):
        try:
            details = get_single_user_details(_
