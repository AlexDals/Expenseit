import streamlit as st

st.title("Employee Expense Reporting")
st.write("Please log in to access your dashboard.")

# --- Retrieve the authenticator object from session state ---
# This was created in app.py and is shared across all pages.
authenticator = st.session_state.get('authenticator')
if not authenticator:
    st.error("Authentication system not initialized. Please run the main app.py file.")
    st.stop()

# --- Render the login form ---
# When the user logs in, this function updates st.session_state
# and automatically triggers a rerun. The main app.py will then
# see the updated login status and show the correct pages.
name, authentication_status, username = authenticator.login()

# --- Display messages based on login status ---
if authentication_status is False:
    st.error("Username/password is incorrect.")
elif authentication_status is None:
    st.warning("Please enter your username and password.")
