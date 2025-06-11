import streamlit as st
from utils import supabase_utils as su

# --- Authentication Guard ---
if not st.session_state.get("authentication_status"):
    st.switch_page("pages/1_Login.py")

# --- Get Session State ---
name = st.session_state.get("name")
username = st.session_state.get("username")

# --- Sidebar ---
st.sidebar.title(f"Welcome {name}!")
st.connections['authenticator'].logout("Logout", "sidebar")

# --- Page Content ---
st.title("Dashboard")
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
        st.error("Could not find your user profile.")
except Exception as e:
    st.error(f"Could not load dashboard: {e}")
