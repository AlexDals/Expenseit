# File: pages/10_Department_Maintenance.py

import streamlit as st
from utils.supabase_utils import init_connection
from utils.ui_utils import hide_streamlit_pages_nav
from utils.nav_utils import PAGES_FOR_ROLES

# Page config
st.set_page_config(page_title="Department Maintenance", layout="wide")

# Hide built-in nav and apply global CSS
hide_streamlit_pages_nav()

# --- Sidebar Navigation (role-based) ---
role = st.session_state.get("role", "logged_out")
st.sidebar.header("Navigation")
for label, fname in PAGES_FOR_ROLES.get(role, PAGES_FOR_ROLES["logged_out"]):
    if fname in ("7_Add_User.py", "8_Edit_User.py"):
        continue
    if st.sidebar.button(label):
        st.switch_page(f"pages/{fname}")

# --- Authentication Guard ---
if not st.session_state.get("authentication_status"):
    st.warning("Please log in to access this page.")
    st.stop()

# Initialize Supabase
supabase = init_connection()

# --- Manage Departments ---
st.header("Manage Departments")
try:
    deps = supabase.table("departments").select("*").order("name", desc=False).execute().data
except Exception as e:
    msg = str(e)
    if "relation \"public.departments\" does not exist" in msg:
        st.info("No `departments` table found. Please create it and reload.")
        st.stop()
    else:
        st.error(f"Error loading departments: {e}")
        st.stop()

# Display each department in a row of 4 columns:
# [Department Name] [Update] [Delete] [Spacer]
for dep in deps:
    col_name, col_update, col_delete, _ = st.columns([4, 1, 1, 1])
    new_name = col_name.text_input(
        "Department Name",
        value=dep["name"],
        key=f"dep_name_{dep['id']}"
    )

    if col_update.button("Update", key=f"update_dep_{dep['id']}"):
        try:
            supabase.table("departments").update({"name": new_name}).eq("id", dep["id"]).execute()
            st.success(f"Renamed '{dep['name']}' → '{new_name}'.")
            st.experimental_rerun()
        except Exception as ex:
            st.error(f"Error updating department: {ex}")

    if col_delete.button("Delete", key=f"delete_dep_{dep['id']}"):
        try:
            supabase.table("departments").delete().eq("id", dep["id"]).execute()
            st.success(f"Deleted department '{dep['name']}'.")
            st.experimental_rerun()
        except Exception as ex:
            st.error(f"Error deleting department: {ex}")

st.markdown("---")

# --- Add New Department ---
st.subheader("Add New Department")
new_dep = st.text_input("Name", key="new_dep_name")
if st.button("Add Department"):
    if not new_dep:
        st.error("Enter a department name.")
    else:
        try:
            # Check for duplicate
            dup = supabase.table("departments").select("id", count="exact").eq("name", new_dep).execute()
            if dup.count > 0:
                st.error(f"A department named '{new_dep}' already exists.")
            else:
                supabase.table("departments").insert({"name": new_dep}).execute()
                st.success(f"Added department '{new_dep}'.")
                st.experimental_rerun()
        except Exception as ex:
            st.error(f"Error adding department: {ex}")
