import streamlit as st
from utils.nav_utils import filter_pages_by_role
filter_pages_by_role()

import pandas as pd
from utils import supabase_utils as su

st.set_page_config(layout="wide", page_title="Dashboard")

# --- Authentication Guard ---
if not st.session_state.get("authentication_status"):
    st.warning("Please log in to access the dashboard.")
    st.stop()

st.subheader("Your Dashboard")
try:
    user_id = st.session_state.get("user_id")
    df = su.get_reports_for_user(user_id)
    if not df.empty:
        c1, c2 = st.columns(2)
        with c1:
            st.metric("Total Reports", len(df))
        with c2:
            st.metric("Total Claimed", f"${df['total_amount'].sum():,.2f}")
    else:
        st.info("No reports submitted yet.")
except Exception as e:
    st.error(f"Could not load dashboard: {e}")
