import streamlit as st
from utils import supabase_utils as su

st.title("Employee Expense Reporting")
st.write("Please log in to access your dashboard.")

# --- Retrieve the authenticator object from session state ---
# This was created in app.py and is shared across all pages.
authenticator = st.session_state.get('authenticator')
if not authenticator:
    st.error("Authentication system not initialized. Please run the main app.py file.")
    st.stop()

# --- Render the login form ---
# This call renders the widget and updates session state on its own.
# It no longer returns a tuple.
authenticator.login()

# --- Check the results from session state ---
if st.session_state.get("authentication_status") is False:
    st.error("Username/password is incorrect.")

elif st.session_state.get("authentication_status") is True:
    # This logic runs immediately after a successful login.
    username = st.session_state.get("username")
    
    # Manually fetch and set the user's role and ID into the session state.
    if username and ('role' not in st.session_state or st.session_state.get('role') is None):
        user_credentials = st.session_state.get('user_credentials', {})
        user_details = user_credentials.get("usernames", {}).get(username, {})
        st.session_state["role"] = user_details.get("role")
        st.session_state["user_id"] = user_details.get("id")
    
    # Switch to the dashboard page upon successful login.
    st.switch_page("pages/2_Dashboard.py")
