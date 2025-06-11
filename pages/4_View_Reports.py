import streamlit as st
from utils import supabase_utils as su
import pandas as pd
import io
import re
import json

# --- Authentication Guard ---
if not st.session_state.get("authentication_status"):
    st.warning("Please log in to access this page.")
    st.stop()

# --- Page Setup and Role/User Info ---
st.title("🗂️ View & Approve Expense Reports")
username = st.session_state.get("username")
user_role = st.session_state.get("role")
user_id = su.get_user_id_by_username(username)

if not user_id:
    st.error("Could not identify user. Please log in again.")
    st.stop()

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

if reports_df.empty:
    st.info("No reports found for your view.")
else:
    # --- Report Selection ---
    if 'user' in reports_df.columns:
        reports_df['submitter_name'] = reports_df['user'].apply(lambda x: x.get('name') if isinstance(x, dict) else 'N/A')
        reports_df['display_name'] = reports_df['report_name'] + " by " + reports_df['submitter_name'] + " (Status: " + reports_df['status'] + ")"
    else:
        reports_df['display_name'] = reports_df['report_name'] + " (Status: " + reports_df['status'] + ")"
    
    report_options = {row['display_name']: row['id'] for index, row in reports_df.iterrows()}
    report_options_list = ["-- Select a report --"] + list(report_options.keys())
    selected_report_display_name = st.selectbox("Select a report to view its details:", options=report_options_list, key="report_selector")

    if selected_report_display_name != "-- Select a report --":
        selected_report_id = report_options[selected_report_display_name]
        
        # Use session state to manage which report is being denied
        if 'denying_report_id' not in st.session_state:
            st.session_state.denying_report_id = None
        
        st.markdown("---")
        st.header(f"Details for: {selected_report_display_name.split(' (')[0]}")
        
        selected_report_details = reports_df[reports_df['id'] == selected_report_id].iloc[0]
        
        # --- Approval & Editing Section (for Admins/Approvers) ---
        if user_role in ['admin', 'approver']:
            st.write(f"**Current Status:** `{selected_report_details['status']}`")
            # If the report was denied, show the reason
            if selected_report_details['status'] == 'Denied' and pd.notna(selected_report_details.get('approver_comment')):
                st.error(f"**Reason for Denial:** {selected_report_details['approver_comment']}")

            # Only show action buttons if the status is 'Submitted'
            if selected_report_details['status'] == 'Submitted':
                st.write("Actions:")
                bcol1, bcol2, bcol3 = st.columns([1, 1, 5])
                with bcol1:
                    if st.button("Approve", type="primary", use_container_width=True):
                        if su.update_report_status(selected_report_id, "Approved"):
                            st.success("Report Approved!")
                            st.rerun()
                with bcol2:
                    # This button now triggers the denial form to appear
                    if st.button("Deny", use_container_width=True):
                        st.session_state.denying_report_id = selected_report_id
                        st.rerun()

            # --- NEW: Denial Reason Form ---
            # This form will only appear if the "Deny" button was clicked for this report
            if st.session_state.denying_report_id == selected_report_id:
                st.markdown("---")
                with st.form("denial_form"):
                    st.subheader("Provide Reason for Denial")
                    denial_reason = st.text_area("Reason*", help="This comment will be saved with the report.")
                    ccol1, ccol2 = st.columns(2)
                    with ccol1:
                        if st.form_submit_button("Confirm Denial", type="primary", use_container_width=True):
                            if denial_reason:
                                if su.update_report_status(selected_report_id, "Denied", comment=denial_reason):
                                    st.warning("Report Denied and comment saved.")
                                    st.session_state.denying_report_id = None # Close form
                                    st.rerun()
                            else:
                                st.error("A reason is required to deny a report.")
                    with ccol2:
                        if st.form_submit_button("Cancel", use_container_width=True):
                            st.session_state.denying_report_id = None # Close form
                            st.rerun()
            st.markdown("---")
            
            # ... (Data Editor logic for editing expenses remains the same) ...

        # --- Static View & Details ---
        expenses_df = su.get_expenses_for_report(selected_report_id)
        if not expenses_df.empty:
             # ... (Display logic for expenses and line items remains the same) ...
        else:
            st.info("No expense items found for this report.")

        # ... (Export buttons logic remains the same) ...
