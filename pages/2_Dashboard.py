# File: pages/2_Dashboard.py

import streamlit as st
from utils import supabase_utils as su
from utils.nav_utils import PAGES_FOR_ROLES
from utils.ui_utils import hide_streamlit_pages_nav

# Page config must come first
st.set_page_config(page_title="Dashboard", layout="wide")

# Hide Streamlit’s built-in multipage nav
hide_streamlit_pages_nav()

# --- Sidebar Navigation (role‐based) ---
role = st.session_state.get("role", "logged_out")
st.sidebar.header("Navigation")
for label, fname in PAGES_FOR_ROLES.get(role, PAGES_FOR_ROLES["logged_out"]):
    if fname.startswith("_"):
        continue
    if st.sidebar.button(label):
        st.switch_page(f"pages/{fname}")

# --- Authentication Guard ---
if not st.session_state.get("authentication_status"):
    st.warning("Please log in to access the dashboard.")
    st.stop()

user_id = st.session_state.get("user_id")
if not user_id:
    st.error("User profile not found in session.")
    st.stop()

# --- Main Dashboard Content ---
st.subheader("Your Dashboard")

try:
    user_reports_df = su.get_reports_for_user(user_id)
    if not user_reports_df.empty:
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Reports Submitted", len(user_reports_df))
        with col2:
            total_amount = user_reports_df["total_amount"].sum()
            st.metric("Total Expenses Claimed", f"${total_amount:,.2f}")
    else:
        st.info("No reports submitted yet. Go to 'New Report' to create one!")
except Exception as e:
    st.error(f"Could not load dashboard: {e}")
