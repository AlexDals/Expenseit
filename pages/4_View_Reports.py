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
user_id = st.session_state.get("user_id")

if not user_id:
    st.error("User profile not found in session. Please log in again.")
    st.stop()

# --- Initialize session state for denial workflow ---
if 'denying_report_id' not in st.session_state:
    st.session_state.denying_report_id = None

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
    # --- Report Selection Dropdown ---
    if 'user' in reports_df.columns:
        reports_df['submitter_name'] = reports_df['user'].apply(lambda x: x.get('name') if isinstance(x, dict) else 'N/A')
        # Handle cases where submitter might be null for orphan reports
        reports_df['submitter_name'] = reports_df['submitter_name'].fillna('Unknown User')
        reports_df['display_name'] = reports_df['report_name'] + " by " + reports_df['submitter_name'] + " (Status: " + reports_df['status'] + ")"
    else:
        reports_df['display_name'] = reports_df['report_name'] + " (Status: " + reports_df['status'] + ")"
    
    # --- FIX: New dropdown logic using unique IDs ---
    # 1. Create a dictionary mapping the UNIQUE ID to the display name
    id_to_display_name_map = {row['id']: row['display_name'] for index, row in reports_df.iterrows()}
    
    # 2. The options for the selectbox are now the unique IDs, with a placeholder
    report_id_options = ["-- Select a report --"] + list(id_to_display_name_map.keys())

    # 3. Use `format_func` to control what the user sees in the dropdown
    selected_report_id = st.selectbox(
        "Select a report to view its details:",
        options=report_id_options,
        format_func=lambda report_id: id_to_display_name_map.get(report_id, "-- Select a report --")
    )
    # --- END OF FIX ---

    if selected_report_id != "-- Select a report --":
        # The selected value is now the ID directly, no lookup needed
        clean_report_name = re.sub(r'[^a-zA-Z0-9\s]', '', id_to_display_name_map[selected_report_id].split(' (')[0]).replace(' ', '_')
        
        st.markdown("---")
        st.header(f"Details for: {id_to_display_name_map[selected_report_id].split(' (')[0]}")
        
        selected_report_details = reports_df[reports_df['id'] == selected_report_id].iloc[0]
        original_expenses_df = su.get_expenses_for_report(selected_report_id)

        # --- Approval & Editing Section (for Admins/Approvers) ---
        if user_role in ['admin', 'approver']:
            st.write(f"**Current Status:** `{selected_report_details['status']}`")
            if pd.notna(selected_report_details.get('approver_comment')):
                st.error(f"**Reason for Denial:** {selected_report_details['approver_comment']}")

            if selected_report_details['status'] == 'Submitted':
                st.write("Actions:")
                bcol1, bcol2, bcol3 = st.columns([1, 1, 5])
                with bcol1:
                    if st.button("Approve", type="primary", use_container_width=True):
                        if su.update_report_status(selected_report_id, "Approved"):
                            st.success("Report Approved!"); st.rerun()
                with bcol2:
                    if st.button("Deny", use_container_width=True):
                        st.session_state.denying_report_id = selected_report_id; st.rerun()
            
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
                                    st.warning("Report Denied."); st.session_state.denying_report_id = None; st.rerun()
                            else: st.error("A reason is required.")
                    with ccol2:
                        if st.form_submit_button("Cancel", use_container_width=True):
                            st.session_state.denying_report_id = None; st.rerun()
            st.markdown("---")
            
            if not original_expenses_df.empty:
                st.subheader("Edit Expense Details")
                # ... (Data editor logic remains the same) ...
        
        # --- Static View for Regular Users ---
        else:
            if not original_expenses_df.empty:
                for index, row in original_expenses_df.iterrows():
                    # ... (Static display logic remains the same) ...
            else:
                st.info("No expense items found for this report.")

        # --- Export Buttons Section ---
        if not original_expenses_df.empty:
            st.subheader("Export This Full Report")
            # ... (Export buttons logic remains the same) ...
