# File: pages/2_Dashboard.py

import streamlit as st
from utils import supabase_utils as su
import pandas as pd
from utils.ui_utils import hide_streamlit_pages_nav

# *First thing* on the page:
hide_streamlit_pages_nav()

st.set_page_config(page_title="Login", layout="wide")
# --- Authentication Guard ---
if not st.session_state.get("authentication_status"):
    st.warning("Please log in to access the dashboard.")
    st.stop()

# --- Retrieve authenticator and user info from session state ---
authenticator = st.session_state.get('authenticator')
user_id       = st.session_state.get('user_id')
if not user_id:
    st.error("User profile not found in session.")
    st.stop()

st.subheader("Your Dashboard")
try:
    user_reports_df = su.get_reports_for_user(user_id)
    if not user_reports_df.empty:
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Reports Submitted", len(user_reports_df))
        with col2:
            st.metric("Total Expenses Claimed", f"${user_reports_df['total_amount'].sum():,.2f}")
    else:
        st.info("No reports submitted yet. Go to 'New Report' to create one!")
except Exception as e:
    st.error(f"Could not load dashboard: {e}")
