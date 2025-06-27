# File: pages/10_Department_Maintenance.py

import streamlit as st
from utils.supabase_utils import init_connection
from utils.ui_utils import hide_streamlit_pages_nav

# *First thing* on the page:
hide_streamlit_pages_nav()

st.set_page_config(page_title="Login", layout="wide")

st.set_page_config(page_title="Department Maintenance", layout="wide")
st.title("Department Maintenance")

supabase = init_connection()

# Fetch all departments
dept_res = supabase.table("departments").select("id, name").order("name", ascending=True).execute()
if dept_res.error:
    st.error(f"Error loading departments: {dept_res.error.message}")
    st.stop()
departments = dept_res.data

# List & edit/delete existing departments
for dept in departments:
    col1, col2, col3 = st.columns([4, 1, 1])
    new_name = col1.text_input(
        "", value=dept["name"], key=f"dept_name_{dept['id']}"
    )
    if col2.button("Update", key=f"update_dept_{dept['id']}"):
        supabase.table("departments").update({"name": new_name}).eq("id", dept["id"]).execute()
        st.success(f"Department renamed to '{new_name}'.")
        st.experimental_rerun()
    if col3.button("Delete", key=f"delete_dept_{dept['id']}"):
        supabase.table("departments").delete().eq("id", dept["id"]).execute()
        st.success(f"Deleted department '{dept['name']}'.")
        st.experimental_rerun()

# Add new department
st.subheader("Add New Department")
new_dept = st.text_input("Name", key="new_dept_name")
if st.button("Add Department"):
    if not new_dept:
        st.error("Enter a department name.")
    else:
        supabase.table("departments").insert({"name": new_dept}).execute()
        st.success(f"Added department '{new_dept}'.")
        st.experimental_rerun()
