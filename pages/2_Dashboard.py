# File: pages/2_Dashboard.py

import streamlit as st
from utils import supabase_utils as su
from utils.ui_utils import hide_streamlit_pages_nav
from utils.nav_utils import PAGES_FOR_ROLES

# Page configuration
st.set_page_config(page_title="Dashboard", layout="wide")

# Hide Streamlit’s built-in multipage nav & apply global CSS
hide_streamlit_pages_nav()

# --- Sidebar Navigation (role‐based) ---
role = st.session_state.get("role", "logged_out")
st.sidebar.header("Navigation")
for label, fname in PAGES_FOR_ROLES.get(role, PAGES_FOR_ROLES["logged_out"]):
    if fname in ("7_Add_User.py", "8_Edit_User.py"):
        continue
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

# --- Dashboard Metrics ---
metrics = []

# If this user is an approver, show how many reports they need to approve
if role == "approver":
    try:
        approver_reports_df = su.get_reports_for_approver(user_id)
        metrics.append(("Reports to Approve", len(approver_reports_df)))
    except Exception as e:
        st.error(f"Could not load reports for approval: {e}")

# Always show the user's own report metrics
try:
    user_reports_df = su.get_reports_for_user(user_id)
except Exception as e:
    st.error(f"Could not load your reports: {e}")
    st.stop()

total_reports = len(user_reports_df)
total_amount  = user_reports_df["total_amount"].sum() if not user_reports_df.empty else 0.0

metrics.append(("Total Reports Submitted", total_reports))
metrics.append(("Total Expenses Claimed", f"${total_amount:,.2f}"))

# Render metrics in equally spaced columns
cols = st.columns(len(metrics))
for col, (label, value) in zip(cols, metrics):
    col.metric(label, value)
