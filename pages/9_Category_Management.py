# File: pages/9_Category_Management.py

import streamlit as st
from utils.supabase_utils import init_connection, get_all_categories, get_all_users, get_single_user_details, update_user_details
from utils.ui_utils import hide_streamlit_pages_nav
from utils.nav_utils import PAGES_FOR_ROLES

# *First thing* on the page:
hide_streamlit_pages_nav()  # :contentReference[oaicite:13]{index=13}

st.set_page_config(page_title="Category Management", layout="wide")
supabase = init_connection()

# --- Sidebar Navigation (role-based) ---
role = st.session_state.get("role", "logged_out")
st.sidebar.header("Navigation")
for label, fname in PAGES_FOR_ROLES.get(role, PAGES_FOR_ROLES["logged_out"]):  # :contentReference[oaicite:14]{index=14}
    if fname in ("7_Add_User.py", "8_Edit_User.py"):
        continue
    if st.sidebar.button(label):
        st.switch_page(f"pages/{fname}")

# --- Authentication Guard ---
if not st.session_state.get("authentication_status"):
    st.warning("Please log in to access this page.")
    st.stop()

# --- 1) CATEGORY CRUD ---
st.header("Manage Categories")
try:
    cat_res = (
        supabase.table("categories")
                 .select("id, name, gl_account")
                 .order("name", desc=False)
                 .execute()
    )
    categories = cat_res.data
except Exception as e:
    st.error(f"Error loading categories: {e}")
    st.stop()

for cat in categories:
    col1, col2, col3 = st.columns([4,1,1])
    new_name = col1.text_input("", value=cat["name"], key=f"cat_name_{cat['id']}")
    new_gl   = col1.text_input("", value=cat.get("gl_account",""), key=f"cat_gl_{cat['id']}")
    if col2.button("Update", key=f"update_cat_{cat['id']}"):
        try:
            supabase.table("categories") \
                    .update({"name": new_name, "gl_account": new_gl}) \
                    .eq("id", cat["id"]) \
                    .execute()
            st.success(f"Renamed category to '{new_name}'.")
            st.experimental_rerun()
        except Exception as e:
            st.error(f"Error updating category: {e}")
    if col3.button("Delete", key=f"delete_cat_{cat['id']}"):
        try:
            supabase.table("categories") \
                    .delete() \
                    .eq("id", cat["id"]) \
                    .execute()
            st.success(f"Deleted category '{cat['name']}'.")
            st.experimental_rerun()
        except Exception as e:
            st.error(f"Error deleting category: {e}")

st.subheader("Add New Category")
new_cat = st.text_input("Name", key="new_cat_name")
new_gl  = st.text_input("GL Account Number", key="new_cat_gl")
if st.button("Add Category"):
    if not new_cat:
        st.error("Enter a category name.")
    else:
        try:
            supabase.table("categories").insert({"name": new_cat, "gl_account": new_gl}).execute()
            st.success(f"Added category '{new_cat}'.")
            st.experimental_rerun()
        except Exception as e:
            st.error(f"Error adding category: {e}")

st.write("---")

# --- 2) ASSIGN DEFAULT CATEGORY TO USER ---
st.header("Assign Default Category to User")
users_df = get_all_users()
users    = users_df.to_dict("records") if hasattr(users_df, "to_dict") else users_df

if not users:
    st.info("No users found to assign.")
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
                st.success(f"Set default category for '{sel_user['name']}' to '{sel_cat_name}'.")
            else:
                st.error("Failed to update user. Check the logs.")
        except Exception as e:
            st.error(f"Error assigning default category: {e}")  # :contentReference[oaicite:15]{index=15}
