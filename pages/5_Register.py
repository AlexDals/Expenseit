import streamlit as st
from utils.nav_utils import filter_pages_by_role
filter_pages_by_role()

import re
import bcrypt
from utils import supabase_utils as su

st.set_page_config(layout="wide", page_title="Register")
st.title("Register New User")

if st.session_state.get("authentication_status"):
    st.warning("You are already logged in.")
    st.stop()

username = st.text_input("Username")
name     = st.text_input("Full Name")
email    = st.text_input("Email")
password = st.text_input("Password", type="password")
role     = st.selectbox("Role", ["user","approver","admin"])

if st.button("Register"):
    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        st.error("Invalid email address.")
    elif not username.isalnum():
        st.error("Username must be alphanumeric.")
    else:
        pwd_bytes = password.encode("utf-8")
        salt      = bcrypt.gensalt()
        hash_b    = bcrypt.hashpw(pwd_bytes, salt)
        hash_str  = hash_b.decode("utf-8")
        if su.register_user(username, name, email, hash_str, role):
            st.success("Registration successful!")
            st.balloons()
        else:
            st.error("Registration failed.")
