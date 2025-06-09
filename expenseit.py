import streamlit as st
import streamlit_authenticator as stauth
from utils import db_utils # Ensure db_utils.init_db() is called on import

st.set_page_config(layout="wide", page_title="Expense Reporting")

# --- USER AUTHENTICATION using Streamlit Secrets ---
# For Streamlit Cloud, you'll set these in your app's secrets via the UI.
# The structure in secrets should mirror the expected config dict.
# Example secrets structure (in Streamlit Cloud > App > Settings > Secrets):
#
# [credentials.usernames.jsmith]
# email = "jsmith@example.com"
# name = "John Smith"
# password = "hashed_password_for_jsmith" # Use streamlit_authenticator.Hasher(['your_password']).generate()
#
# [credentials.usernames.adoe]
# email = "adoe@example.com"
# name = "Alice Doe"
# password = "hashed_password_for_adoe"
#
# [cookie]
# expiry_days = 30
# key = "some_random_signature_key"
# name = "some_cookie_name"
#
# [preauthorized]
# emails = ["user1@example.com", "user2@example.com"] # Optional

try:
    # Attempt to load credentials from Streamlit secrets
    credentials = st.secrets.get("credentials", {})
    cookie_config = st.secrets.get("cookie", {})
    preauthorized_config = st.secrets.get("preauthorized", {})

    if not credentials or not cookie_config:
        st.error("Authentication configuration is missing from Streamlit Secrets. Please set them up.")
        st.caption("Refer to `streamlit_app.py` comments for the required secrets structure.")
        st.stop()

    authenticator = stauth.Authenticate(
        credentials,
        cookie_config.get('name', 'some_cookie_name'), # Provide defaults if key might be missing
        cookie_config.get('key', 'some_random_signature_key'),
        cookie_config.get('expiry_days', 30),
        preauthorized_config.get('emails', [])
    )

except Exception as e:
    st.error(f"Error loading authentication configuration from secrets: {e}")
    st.stop()


# Initialize database (creates tables if they don't exist)
# db_utils.init_db() # This is now called when db_utils is imported

name, authentication_status, username = authenticator.login()

if authentication_status == False:
    st.error("Username/password is incorrect")
elif authentication_status == None:
    st.warning("Please enter your username and password")
elif authentication_status:
    st.sidebar.title(f"Welcome {st.session_state.get('name', '')}!") # Use name from session state
    authenticator.logout("Logout", "sidebar")

    st.title("Employee Expense Reporting App")
    st.write("Navigate using the sidebar to create a new report or view existing reports.")
    st.markdown("---")
    st.subheader("Quick Stats (Example)")
    try:
        user_reports_df = db_utils.get_reports_for_user(st.session_state.get("username"))
        if not user_reports_df.empty:
            st.metric("Total Reports Submitted", len(user_reports_df))
            st.metric("Total Expenses Claimed", f"${user_reports_df['total_amount'].sum():,.2f}")
        else:
            st.info("No reports submitted yet.")
    except Exception as e:
        st.error(f"Could not load stats: {e}")
        st.warning("Note: On Streamlit Cloud, the SQLite database might be reset if the app sleeps or restarts. For persistent data, consider a cloud database.")

# Registration (Optional, if you want users to register themselves)
# This part is more complex with Streamlit Secrets as you can't directly write back to them.
# You would typically pre-populate users or have an admin interface if using secrets directly.
# If self-registration is needed with dynamic updates, a proper database backend for users is better.
#
# if not authentication_status:
#     try:
#         if authenticator.register_user('Register user', preauthorization=False): # Set preauthorization based on your needs
#             st.success('User registered successfully! Please ask an admin to update the secrets if this is a shared app, or re-deploy if managing secrets directly.')
#             # NOTE: Registering users like this won't persist them in st.secrets without manual update and redeploy.
#             # For dynamic user bases, a proper database for user management is recommended over st.secrets.
#     except Exception as e:
#         st.error(e)
