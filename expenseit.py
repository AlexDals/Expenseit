import streamlit as st
import streamlit_authenticator as stauth
from utils import supabase_utils as su

st.set_page_config(layout="wide", page_title="Expense Reporting")

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

name, authentication_status, username = authenticator.login()

if authentication_status == False:
    st.error("Username/password is incorrect")
elif authentication_status == None:
    st.warning("Please enter your username and password")
    st.info("New user? Navigate to the **Register** page from the sidebar.")
elif authentication_status:
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
                st.metric("Total Reports Submitted", len(user_reports_df))
                st.metric("Total Expenses Claimed", f"${user_reports_df['total_amount'].sum():,.2f}")
            else:
                st.info("No reports submitted yet. Go to 'New Report' to create one!")
        else:
            st.error("Could not find your user profile. Please contact support.")
    except Exception as e:
        st.error(f"Could not load dashboard: {e}")
