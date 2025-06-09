import streamlit as st
import re
from utils import supabase_utils as su
import bcrypt # Import bcrypt directly

st.set_page_config(page_title="Register", layout="centered")
st.title("Register New User")

# Prevent logged-in users from accessing the registration page
if st.session_state.get("authentication_status"):
    st.warning("You are already logged in. Please log out to register a new user.")
    st.stop()

# Regex for basic email validation
EMAIL_REGEX = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"

with st.form("registration_form"):
    st.write("Please fill out the details below to register.")
    email = st.text_input("Email*", help="A valid email address.")
    name = st.text_input("Full Name*", help="Your full name.")
    username = st.text_input("Username*", help="Must be alphanumeric with no spaces.")
    password = st.text_input("Password*", type="password")
    confirm_password = st.text_input("Confirm Password*", type="password")
    submitted = st.form_submit_button("Register")

if submitted:
    # --- Form Validation ---
    if not all([email, name, username, password, confirm_password]):
        st.error("Please fill out all mandatory fields marked with *.")
    elif password != confirm_password:
        st.error("Passwords do not match.")
    elif not re.match(EMAIL_REGEX, email):
        st.error("Invalid email address.")
    elif " " in username or not username.isalnum():
        st.error("Username must be alphanumeric with no spaces.")
    else:
        # --- Registration Logic ---
        try:
            # --- HASHING LOGIC CHANGED ---
            # We now use bcrypt directly to create the hashed password.
            # 1. Encode the plain-text password to bytes.
            password_bytes = password.encode('utf-8')
            # 2. Generate a salt and hash the password.
            salt = bcrypt.gensalt()
            hashed_password_bytes = bcrypt.hashpw(password_bytes, salt)
            # 3. Decode the hashed password bytes back to a string for storing in the database.
            hashed_password_str = hashed_password_bytes.decode('utf-8')
            
            # --- End of Hashing Logic Change ---

            if su.register_user(username, name, email, hashed_password_str):
                st.success("Registration successful! You can now log in from the main page.")
                st.balloons()
            # The register_user function will show specific errors from Supabase
        except Exception as e:
            st.error(f"A critical error occurred during hashing or registration: {e}")
