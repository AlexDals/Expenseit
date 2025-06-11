import streamlit as st
from utils import supabase_utils as su

# --- PAGE CONFIGURATION ---
# Set the page config once, here at the top of the main script.
st.set_page_config(layout="wide", page_title="Expense Reporting")

# --- AUTHENTICATION AND SESSION STATE INITIALIZATION ---
# This part is similar to the start of our old main file.
try:
    user_credentials = su.fetch_all_users_for_auth()
    cookie_config = st.secrets.get("cookie", {})
    authenticator = st.connections['authenticator'].authenticate(user_credentials)
except Exception as e:
    st.error(f"An error occurred during authentication setup: {e}")
    st.stop()

# --- PROGRAMMATIC NAVIGATION ---
# Define all possible pages in your app.
login_page = st.Page("pages/1_Login.py", title="Login", icon="🔑", default=True)
dashboard_page = st.Page("pages/2_Dashboard.py", title="Dashboard", icon="🏠")
new_report_page = st.Page("pages/3_New_Report.py", title="New Report", icon="📄")
view_reports_page = st.Page("pages/4_View_Reports.py", title="View Reports", icon="🗂️")
register_page = st.Page("pages/5_Register.py", title="Register", icon="🔑")
admin_page = st.Page("pages/6_User_Management.py", title="User Management", icon="⚙️")

# Define the navigation structure based on the user's role and login status.
account_pages = [login_page, register_page]
app_pages = [dashboard_page, new_report_page, view_reports_page]

# Build the final page list
if st.session_state.get("authentication_status"):
    # If the user is logged in
    nav_pages = app_pages
    if st.session_state.get("role") == 'admin':
        nav_pages.append(admin_page)
else:
    # If the user is logged out
    nav_pages = account_pages

# Create the navigation object from the filtered list of pages
pg = st.navigation(nav_pages)

# Run the app by calling the navigation object
pg.run()
