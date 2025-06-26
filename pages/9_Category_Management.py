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

# Fetch all categories (no .order), then sort locally
try:
    cat_res = supabase.table("categories").select("id, name").execute()
    categories = cat_res.data or []
    # Sort by name ascending
    categories.sort(key=lambda c: c["name"].lower())
except Exception as e:
    st.error(f"Could not load categories: {e}")
    st.stop()

# List existing categories with inline edit/delete
for cat in categories:
    col1, col2, col3 = st.columns([4, 1, 1])
    new_name = col1.text_input("", value=cat["name"], key=f"cat_name_{cat['id']}")
    if col2.button("Update", key=f"update_cat_{cat['id']}"):
        try:
            supabase.table("categories").update({"name": new_name}).eq("id", cat["id"]).execute()
            st.success(f"Category renamed to '{new_name}'.")
            st.experimental_rerun()
        except Exception as e:
            st.error(f"Error updating category: {e}")
    if col3.button("Delete", key=f"delete_cat_{cat['id']}"):
        try:
            supabase.table("categories").delete().eq("id", cat["id"]).execute()
            st.success(f"Deleted category '{cat['name']}'.")
            st.experimental_rerun()
        except Exception as e:
            st.error(f"Error deleting category: {e}")

# Add new category
st.subheader("Add New Category")
new_cat = st.text_input("Name", key="new_cat_name")
if st.button("Add Category"):
    if not new_cat:
        st.error("Please enter a category name.")
    else:
        try:
            supabase.table("categories").insert({"name": new_cat}).execute()
            st.success(f"Added new category '{new_cat}'.")
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
            # Reload user details so we preserve role & approver
            details = get_single_user_details(sel_user["id"])
            success = update_user_details(
                sel_user["id"],
                role=details["role"],
                approver_id=details.get("approver_id"),
                default_category_id=sel_cat_id,
            )
            if success:
                st.success(f"Default category for '{sel_user['name']}' set to '{sel_cat_name}'.")
            else:
                st.error("Failed to update user—check the logs.")
        except Exception as e:
            st.error(f"Error assigning category: {e}")
