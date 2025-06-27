import streamlit as st
from utils.nav_utils import filter_pages_by_role
filter_pages_by_role()

from utils.supabase_utils import init_connection

st.set_page_config(layout="wide", page_title="Department Maintenance")
st.title("Department Maintenance")

supabase = init_connection()

# Delete existing departments
# ... your delete logic ...

st.subheader("Add New Department")
newd = st.text_input("Name")
if st.button("Add Department"):
    if newd:
        supabase.table("departments").insert({"name": newd}).execute()
        st.success("Department added.")
    else:
        st.error("Enter a name.")
