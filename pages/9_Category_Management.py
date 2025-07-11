# File: pages/9_Category_Management.py

import streamlit as st
from utils.supabase_utils import init_connection, get_all_users, get_single_user_details, update_user_details
from utils.ui_utils import hide_streamlit_pages_nav
from utils.nav_utils import PAGES_FOR_ROLES

# Page setup
st.set_page_config(page_title="Category Management", layout="wide")
hide_streamlit_pages_nav()

# Sidebar – role‐based nav
role = st.session_state.get("role", "logged_out")
st.sidebar.header("Navigation")
for label, fname in PAGES_FOR_ROLES.get(role, PAGES_FOR_ROLES["logged_out"]):
    if fname in ("7_Add_User.py", "8_Edit_User.py"):
        continue
    if st.sidebar.button(label):
        st.switch_page(f"pages/{fname}")

# Auth guard
if not st.session_state.get("authentication_status"):
    st.warning("Please log in to access this page.")
    st.stop()

supabase = init_connection()

# --- 1) CATEGORY CRUD ---
st.header("Manage Categories")
try:
    resp       = supabase.table("categories").select("id, name, gl_account").order("name", desc=False).execute()
    categories = resp.data
except Exception as e:
    st.error(f"Error loading categories: {e}")
    st.stop()

for cat in categories:
    col_name, col_gl, col_update, col_delete = st.columns([3, 3, 1, 1])
    new_name = col_name.text_input("Category Name", value=cat["name"], key=f"cat_name_{cat['id']}")
    new_gl   = col_gl.text_input  ("GL Account",     value=cat.get("gl_account",""), key=f"cat_gl_{cat['id']}")

    # Update button
    if col_update.button("Update", key=f"update_cat_{cat['id']}"):
        try:
            supabase.table("categories") \
                    .update({"name": new_name, "gl_account": new_gl}) \
                    .eq("id", cat["id"]) \
                    .execute()
            st.success(f"Updated '{cat['name']}' → '{new_name}' (GL {new_gl}).")
            st.experimental_rerun()
        except Exception as ex:
            st.error(f"Error updating category: {ex}")

    # Delete button with dependency checks
    if col_delete.button("Delete", key=f"delete_cat_{cat['id']}"):
        # 1) Used in any expense items?
        used = supabase.table("expenses") \
                       .select("id", count="exact") \
                       .eq("category_id", cat["id"]) \
                       .execute().count
        if used > 0:
            st.error("Cannot delete: this category has been used in expense items.")
            continue

        # 2) Assigned as default to any user?
        assigned = supabase.table("users") \
                           .select("id", count="exact") \
                           .eq("default_category_id", cat["id"]) \
                           .execute().count
        if assigned > 0:
            st.error("Cannot delete: this category is the default for one or more users.")
            continue

        # Safe to delete
        try:
            supabase.table("categories").delete().eq("id", cat["id"]).execute()
            st.success(f"Deleted category '{cat['name']}'.")
            st.experimental_rerun()
        except Exception as ex:
            st.error(f"Error deleting category: {ex}")

st.markdown("---")

# --- 2) ASSIGN DEFAULT CATEGORY TO USER ---
st.header("Assign Default Category to User")
users_df = get_all_users()
users    = users_df.to_dict("records") if hasattr(users_df, "to_dict") else users_df

if not users:
    st.info("No users to assign.")
else:
    user_labels    = [f"{u['name']} ({u['username']})" for u in users]
    sel_user_label = st.selectbox("Select User", options=user_labels, key="assign_user")
    sel_user       = users[user_labels.index(sel_user_label)]

    cat_labels     = [c["name"] for c in categories]
    sel_cat_name   = st.selectbox("Select Default Category", options=cat_labels, key="assign_cat")
    sel_cat_id     = next(c["id"] for c in categories if c["name"] == sel_cat_name)

    if st.button("Assign Default Category"):
        try:
            details = get_single_user_details(sel_user["id"])
            ok = update_user_details(
                sel_user["id"],
                role=details["role"],
                approver_id=details.get("approver_id"),
                default_category_id=sel_cat_id,
            )
            if ok:
                st.success(f"Set default category for '{sel_user['name']}' → '{sel_cat_name}'.")
            else:
                st.error("Failed to update user.")
        except Exception as e:
            st.error(f"Error assigning default category: {e}")
