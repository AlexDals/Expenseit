import streamlit as st
from utils import supabase_utils as su
import pandas as pd
import io
import re
import json

if not st.session_state.get("authentication_status"):
    st.warning("Please log in to access this page.")
    st.stop()

st.title("🗂️ View & Approve Expense Reports")
username = st.session_state.get("username")
user_role = st.session_state.get("role")
user_id = su.get_user_id_by_username(username)
if not user_id: st.error("Could not identify user."); st.stop()

# Data Fetching Based on Role
reports_df = pd.DataFrame()
page_subheader = ""
if user_role == 'user':
    page_subheader = "Your Submitted Reports"
    reports_df = su.get_reports_for_user(user_id)
elif user_role == 'approver':
    page_subheader = "Reports Awaiting Your Approval"
    reports_df = su.get_reports_for_approver(user_id)
elif user_role == 'admin':
    page_subheader = "All Company Reports"
    reports_df = su.get_all_reports()
st.subheader(page_subheader)

if reports_df.empty:
    st.info("No reports found for your view.")
else:
    # Join user name for display if available
    if 'user' in reports_df.columns:
        reports_df['submitter_name'] = reports_df['user'].apply(lambda x: x.get('name') if isinstance(x, dict) else 'N/A')
        reports_df['display_name'] = reports_df['report_name'] + " by " + reports_df['submitter_name'] + " (Status: " + reports_df['status'] + ")"
    else:
        reports_df['display_name'] = reports_df['report_name'] + " (Status: " + reports_df['status'] + ")"

    report_options = {row['display_name']: row['id'] for index, row in reports_df.iterrows()}
    report_options_list = ["-- Select a report --"] + list(report_options.keys())
    selected_report_display_name = st.selectbox("Select a report to view its details:", options=report_options_list)

    if selected_report_display_name != "-- Select a report --":
        selected_report_id = report_options[selected_report_display_name]
        clean_report_name = re.sub(r'[^a-zA-Z0-9\s]', '', selected_report_display_name.split(' (')[0]).replace(' ', '_')
        st.markdown("---")
        st.header(f"Details for: {selected_report_display_name.split(' (')[0]}")
        
        selected_report_details = reports_df[reports_df['id'] == selected_report_id].iloc[0]
        expenses_df = su.get_expenses_for_report(selected_report_id)
        
        if user_role in ['admin', 'approver']:
            # ... (Approval buttons logic remains the same) ...

        if not expenses_df.empty:
            for index, row in expenses_df.iterrows():
                st.markdown(f"#### Expense: {row.get('vendor', 'N/A')} - ${row.get('amount', 0):.2f}")
                exp_col1, exp_col2 = st.columns(2)
                with exp_col1:
                    st.write(f"**Date:** {row.get('expense_date', 'N/A')}")
                    st.write(f"**Category:** `{row.get('category_name', 'N/A')}`") # Display overall category
                    st.write(f"**Purpose:** {row.get('description', 'N/A')}")
                with exp_col2:
                    # ... (tax display logic remains the same) ...

                with st.expander("View Details (Line Items & Receipt)"):
                    line_items = []
                    if row.get('line_items') and isinstance(row['line_items'], str):
                        try: line_items = json.loads(row['line_items'])
                        except (json.JSONDecodeError, TypeError): line_items = []
                    
                    if line_items and isinstance(line_items, list) and len(line_items) > 0:
                        st.write("**Line Items**")
                        line_items_df = pd.DataFrame(line_items).rename(columns={"category_name": "Category"})
                        st.dataframe(line_items_df)
                    else:
                        st.write("*No line items were extracted for this expense.*")

                    # ... (receipt image logic remains the same) ...
        else:
            st.info("No expense items found for this report.")

        # ... (Export buttons logic remains the same) ...
