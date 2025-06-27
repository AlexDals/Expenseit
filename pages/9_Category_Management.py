import streamlit as st
from utils.nav_utils import filter_pages_by_role
filter_pages_by_role()

from utils.supabase_utils import (
    init_connection,
    get_all_categories,
    get_all_users,
    get_single_user_details,
    update_user_details,
)

st.set_page_config(layout="wide", page_title="Category Management")
supabase = init_connection()

st.header("Manage Categories")
# ... your existing CRUD logic for categories and GL account field ...

st.header("Assign Default Category")
users = get_all_users().to_dict("records")
if users:
    sel = st.selectbox("User", [f"{u['name']} ({u['username']})" for u in users])
    uid = users[[f"{u['name']} ({u['username']})" for u in users].index(sel)]["id"]
    cats = get_all_categories().to_dict("records")
    selc = st.selectbox("Category", [c["name"] for c in cats])
    cid  = next(c["id"] for c in cats if c["name"]==selc)
    if st.button("Assign"):
        det = get_single_user_details(uid)
        ok  = update_user_details(
            uid, role=det["role"], approver_id=det.get("approver_id"), default_category_id=cid
        )
        if ok: st.success("Category assigned.")
        else:  st.error("Failed.")
else:
    st.info("No users.")
