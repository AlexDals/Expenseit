import streamlit as st

PAGES_FOR_ROLES = {
    "admin": [
        ("Dashboard",             "2_Dashboard.py"),
        ("New Report",            "3_New_Report.py"),
        ("View Reports",          "4_View_Reports.py"),
        ("User Management",       "6_Users.py"),
        ("Category Management",   "9_Category_Management.py"),
        ("Department Maintenance","10_Department_Maintenance.py"),
        ("Add User",              "7_Add_User.py"),
        ("Edit User",             "8_Edit_User.py"),
    ],
    "approver": [
        ("Dashboard",   "2_Dashboard.py"),
        ("New Report",  "3_New_Report.py"),
        ("View Reports","4_View_Reports.py"),
    ],
    "user": [
        ("Dashboard",   "2_Dashboard.py"),
        ("New Report",  "3_New_Report.py"),
        ("View Reports","4_View_Reports.py"),
    ],
    "logged_out": [
        ("Login",    "1_Login.py"),
        ("Register", "5_Register.py"),
    ],
}

def filter_pages_by_role():
    """
    Prune Streamlit's built-in pages list so that only pages in
    PAGES_FOR_ROLES[current_role] are shown in the sidebar.
    Must be called at the top of every page.
    """
    role = st.session_state.get("role", "logged_out")
    allowed = {fname for (_lbl, fname) in PAGES_FOR_ROLES.get(role, [])}

    pages = st.experimental_get_pages()
    filtered = {
        page_name: info
        for page_name, info in pages.items()
        if info.path.split("/")[-1] in allowed
    }
    st.experimental_set_pages(filtered)
