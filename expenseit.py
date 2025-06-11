import streamlit as st
import streamlit_authenticator as stauth
from utils import supabase_utils as su

# --- PAGE CONFIGURATION ---
st.set_page_config(layout="wide", page_title="Expense Reporting")


# --- USER AUTHENTICATION ---
try:
    user_credentials = su.fetch_all_users_for_auth()
    cookie_config = st.secrets.get("cookie", {})
    if not cookie_config.get('name') or not cookie_config.get('key'):
        st.error("Cookie configuration is missing from secrets. Please set `name` and `key` under a [cookie] section.")
        st.stop()

    authenticator = stauth.Authenticate(
        user_credentials,
        cookie_config['name'],
        cookie_config['key'],
        cookie_config.get('expiry_days', 30),
    )
except Exception as e:
    st.error(f"An error occurred during authentication setup: {e}")
    st.stop()


# --- LOGIN WIDGET AND LOGIC ---
authenticator.login()


if st.session_state.get("authentication_status") is False:
    st.error("Username/password is incorrect")
    if st.button("Register a new account"):
        st.switch_page("pages/3_🔑_Register.py")

elif st.session_state.get("authentication_status") is None:
    st.warning("Please enter your username and password.")
    if st.button("Register a new account"):
        st.switch_page("pages/3_🔑_Register.py")

elif st.session_state.get("authentication_status"):

    # --- TEMPORARY DEBUGGING CODE ---
    st.warning("Debug Information (This block can be removed after we solve the issue):")
    st.write("Full session state data:")
    st.json(st.session_state)
    # --- END OF DEBUGGING CODE ---
    
    # --- MAIN APP FOR LOGGED-IN USER ---
    name = st.session_state.get("name")
    username = st.session_state.get("username")
    
    st.sidebar.title(f"Welcome {name}!")
    authenticator.logout("Logout", "sidebar")

    st.title("Employee Expense Reporting App")
    st.write("Navigate using the sidebar to create a new report or view existing reports.")
    st.markdown("---")

    st.subheader("Your Dashboard")
    try:
        user_id = su.get_user_id_by_username(username)
        if user_id:
            user_reports_df = su.get_reports_for_user(user_id)
            if not user_reports_df.empty:
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Total Reports Submitted", len(user_reports_df))
                with col2:
                    st.metric("Total Expenses Claimed", f"${user_reports_df['total_amount'].sum():,.2f}")
            else:
                st.info("No reports submitted yet. Go to 'New Report' to create one!")
        else:
            st.error("Could not find your user profile. Please contact support.")
    except Exception as e:
        st.error(f"Could not load dashboard: {e}")
