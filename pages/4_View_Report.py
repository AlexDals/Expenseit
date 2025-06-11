import streamlit as st
from utils import supabase_utils as su
import pandas as pd
import io
import re
import json

# --- Authentication and Role Check ---
if not st.session_state.get("authentication_status"):
    st.warning("Please log in to access this page.")
    st.stop()

st.title("🗂️ View & Approve Expense Reports")

username = st.session_state.get("username")
user_role = st.session_state.get("role")
user_id = su.get_user_id_by_username(username)

if not user_id:
    st.error("Could not identify user. Please log in again."); st.stop()

# --- Data Fetching Based on Role ---
reports_df = pd.DataFrame()
if user_role == 'user':
    st.subheader("Your Submitted Reports")
    reports_df = su.get_reports_for_user(user_id)
elif user_role == 'approver':
    st.subheader("Reports Awaiting Your Approval")
    reports_df = su.get_reports_for_approver(user_id)
elif user_role == 'admin':
    st.subheader("All Company Reports")
    reports_df = su.get_all_reports()

# --- Display Reports and Details ---
if reports_df.empty:
    st.info("No reports found for your view.")
else:
    # Display the list of reports
    reports_df['display_name'] = reports_df['report_name'] + " (Status: " + reports_df['status'] + ")"
    report_options = {row['display_name']: row['id'] for index, row in reports_df.iterrows()}
    report_options_list = ["-- Select a report --"] + list(report_options.keys())
    
    selected_report_display_name = st.selectbox("Select a report to view details:", options=report_options_list)

    if selected_report_display_name != "-- Select a report --":
        selected_report_id = report_options[selected_report_display_name]
        
        # Get details for the selected report
        selected_report_details = reports_df[reports_df['id'] == selected_report_id].iloc[0]
        expenses_df = su.get_expenses_for_report(selected_report_id)
        
        # --- NEW: Approval Action Buttons ---
        if user_role in ['admin', 'approver']:
            st.markdown("---")
            st.write(f"**Current Status:** {selected_report_details['status']}")
            
            # Only show buttons if the status is 'Submitted'
            if selected_report_details['status'] == 'Submitted':
                col1, col2, col3 = st.columns([1,1,5])
                with col1:
                    if st.button("Approve", type="primary", use_container_width=True):
                        su.update_report_status(selected_report_id, "Approved")
                        st.success("Report Approved!")
                        st.rerun()
                with col2:
                    if st.button("Deny", use_container_width=True):
                        su.update_report_status(selected_report_id, "Denied")
                        st.warning("Report Denied.")
                        st.rerun()
            st.markdown("---")

        # Display expense details (existing logic)
        if not expenses_df.empty:
            # ... (the code to display the expense items and line items is the same as before) ...
            for index, row in expenses_df.iterrows():
                # ... display logic from previous version ...
        else:
            st.info("No expense items found for this report.")

        # Export buttons (existing logic)
        # ... (the code for CSV/Excel export is the same as before) ...
