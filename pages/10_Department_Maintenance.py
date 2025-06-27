# File: pages/10_Department_Maintenance.py

import streamlit as st
from utils.supabase_utils import init_connection
from utils.ui_utils import hide_streamlit_pages_nav
from utils.nav_utils import PAGES_FOR_ROLES

# Page configuration
st.set_page_config(page_title="Department Maintenance", layout="wide")

# Hide Streamlit’s built-in multipage nav
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

# Initialize Supabase client
supabase = init_connection()

# --- Load Departments ---
st.header("Manage Departments")
try:
    deps = (
        supabase
        .table("departments")
        .select("*")
        .order("name", desc=False)
        .execute()
        .data
    )
except Exception as e:
    msg = str(e)
    if "relation \"public.departments\" does not exist" in msg:
        st.info(
            "No `departments` table found in your database.\n\n"
            "Please create a table named `departments` with at least:\n"
            "- `id` (UUID PRIMARY KEY DEFAULT uuid_generate_v4()) or BIGSERIAL\n"
            "- `name` TEXT NOT NULL\n"
            "- `created_at` TIMESTAMPTZ DEFAULT NOW()\n\n"
            "Then reload this page."
        )
        st.stop()
    else:
        st.error(f"Error loading departments: {e}")
        st.stop()

# --- Existing Departments (with duplicate‐safe update & delete) ---
for dep in deps:
    col1, col2, col3 = st.columns([4, 1, 1])
    new_name = col1.text_input("", value=dep["name"], key=f"dep_name_{dep['id']}")
    if col2.button("Update", key=f"update_dep_{dep['id']}"):
        try:
            # Prevent duplicate names on update
            dup = supabase.table("departments") \
                          .select("id", count="exact") \
                          .eq("name", new_name) \
                          .neq("id", dep["id"]) \
                          .execute()
            if dup.count > 0:
                st.error(f"A department named '{new_name}' already exists.")
            else:
                supabase.table("departments") \
                        .update({"name": new_name}) \
                        .eq("id", dep["id"]) \
                        .execute()
                st.success(f"Renamed department to '{new_name}'.")
                st.rerun()
        except Exception as ex:
            st.error(f"Error updating department: {ex}")
    if col3.button("Delete", key=f"delete_dep_{dep['id']}"):
        try:
            supabase.table("departments").delete().eq("id", dep["id"]).execute()
            st.success(f"Deleted department '{dep['name']}'.")
            st.rerun()
        except Exception as ex:
            st.error(f"Error deleting department: {ex}")

# --- Add New Department (with duplicate check) ---
st.subheader("Add New Department")
new_dep = st.text_input("Name", key="new_dep_name")
if st.button("Add Department"):
    if not new_dep:
        st.error("Enter a department name.")
    else:
        try:
            # Prevent duplicate names on insert
            dup = supabase.table("departments") \
                          .select("id", count="exact") \
                          .eq("name", new_dep) \
                          .execute()
            if dup.count > 0:
                st.error(f"A department named '{new_dep}' already exists.")
            else:
                supabase.table("departments").insert({"name": new_dep}).execute()
                st.success(f"Added department '{new_dep}'.")
                st.rerun()
        except Exception as ex:
            if "relation \"public.departments\" does not exist" in str(ex):
                st.error("Cannot add department: `departments` table does not exist.")
            else:
                st.error(f"Error adding department: {ex}")
