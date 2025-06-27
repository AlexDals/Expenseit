# File: pages/10_Department_Maintenance.py

import streamlit as st
from utils.supabase_utils import init_connection
from utils.ui_utils import hide_streamlit_pages_nav
from utils.nav_utils import PAGES_FOR_ROLES

# *First thing* on the page:
hide_streamlit_pages_nav()  # :contentReference[oaicite:16]{index=16}

st.set_page_config(page_title="Department Maintenance", layout="wide")
supabase = init_connection()

# --- Sidebar Navigation (role-based) ---
role = st.session_state.get("role", "logged_out")
st.sidebar.header("Navigation")
for label, fname in PAGES_FOR_ROLES.get(role, PAGES_FOR_ROLES["logged_out"]):  # :contentReference[oaicite:17]{index=17}
    if fname in ("7_Add_User.py", "8_Edit_User.py"):
        continue
    if st.sidebar.button(label):
        st.switch_page(f"pages/{fname}")

# --- Authentication Guard ---
if not st.session_state.get("authentication_status"):
    st.warning("Please log in to access this page.")
    st.stop()

# --- Main Department Maintenance Content ---
st.header("Manage Departments")
try:
    deps = supabase.table("departments").select("*").order("name", desc=False).execute().data
except Exception as e:
    st.error(f"Error loading departments: {e}")
    st.stop()

for dep in deps:
    col1, col2 = st.columns([4,1])
    new_name = col1.text_input("", value=dep["name"], key=f"dep_name_{dep['id']}")
    if col2.button("Update", key=f"update_dep_{dep['id']}"):
        try:
            supabase.table("departments").update({"name": new_name}).eq("id", dep["id"]).execute()
            st.success(f"Renamed department to '{new_name}'.")
            st.experimental_rerun()
        except Exception as e:
            st.error(f"Error updating department: {e}")
    if col2.button("Delete", key=f"delete_dep_{dep['id']}"):
        try:
            supabase.table("departments").delete().eq("id", dep["id"]).execute()
            st.success(f"Deleted department '{dep['name']}'.")
            st.experimental_rerun()
        except Exception as e:
            st.error(f"Error deleting department: {e}")

st.subheader("Add New Department")
new_dep = st.text_input("Name", key="new_dep_name")
if st.button("Add Department"):
    if not new_dep:
        st.error("Enter a department name.")
    else:
        try:
            supabase.table("departments").insert({"name": new_dep}).execute()
            st.success(f"Added department '{new_dep}'.")
            st.experimental_rerun()
        except Exception as e:
            st.error(f"Error adding department: {e}")  # :contentReference[oaicite:18]{index=18}
