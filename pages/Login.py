import streamlit as st
import streamlit_authenticator as stauth
from utils import supabase_utils as su

st.title("Employee Expense Reporting")

# --- Re-initialize authenticator on this page ---
# This is necessary because st.navigation runs pages as separate scripts
user_credentials = su.fetch_all_users_for_auth()
cookie_config = st.secrets.get("cookie", {})
authenticator = st.connections['authenticator'].authenticate(user_credentials)

# --- Render Login Widget ---
authenticator.login()

if st.session_state.get("authentication_status") is False:
    st.error("Username/password is incorrect")

elif st.session_state.get("authentication_status") is None:
    st.warning("Please enter your username and password.")

elif st.session_state.get("authentication_status"):
    # This logic runs after a successful login
    username = st.session_state.get("username")
    if username:
        # Manually set the role in the session state
        st.session_state["role"] = su.get_user_role(username)
    
    # Switch to the dashboard page upon successful login
    st.switch_page("pages/2_Dashboard.py")
