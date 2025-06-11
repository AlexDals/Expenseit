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
    st.error("Could not identify user."); st.stop()

# --- Data Fetching ---
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
    selected_report_display_name = st.selectbox("Select a report to view its details:", options=report_options_list)

    if selected_report_display_name != "-- Select a report --":
        selected_report_id = report_options[selected_report_display_name]
        st.markdown("---")
        st.header(f"Details for: {selected_report_display_name.split(' (')[0]}")
        
        selected_report_details = reports_df[reports_df['id'] == selected_report_id].iloc[0]
        expenses_df = su.get_expenses_for_report(selected_report_id)

        # --- Approval & Editing Section (for Admins/Approvers) ---
        if user_role in ['admin', 'approver']:
            # Approval buttons
            st.write(f"**Current Status:** `{selected_report_details['status']}`")
            if selected_report_details['status'] == 'Submitted':
                st.write("Actions:")
                bcol1, bcol2, bcol3 = st.columns([1, 1, 5])
                if bcol1.button("Approve", type="primary", use_container_width=True):
                    if su.update_report_status(selected_report_id, "Approved"): st.success("Report Approved!"); st.rerun()
                if bcol2.button("Deny", use_container_width=True):
                    if su.update_report_status(selected_report_id, "Denied"): st.warning("Report Denied."); st.rerun()
            st.markdown("---")
            
            # Interactive Data Editor
            st.subheader("Edit Expense Details")
            st.info("You can edit the values directly in the table below. Click the 'Save Expense Changes' button when you are done.")
            
            # Fetch categories for the editor dropdown
            categories = su.get_all_categories()
            category_names = [cat['name'] for cat in categories]
            category_map = {cat['name']: cat['id'] for cat in categories}
            
            edited_expenses_df = st.data_editor(
                expenses_df,
                column_config={
                    "id": None, "report_id": None, "user_id": None, "receipt_path": None, 
                    "ocr_text": None, "line_items": None, "created_at": None, "category_id": None,
                    "expense_date": st.column_config.DateColumn("Date", required=True),
                    "vendor": "Vendor",
                    "description": "Purpose",
                    "amount": st.column_config.NumberColumn("Total", format="$%.2f", required=True),
                    "category_name": st.column_config.SelectboxColumn("Category", options=category_names, required=True),
                    "gst_amount": st.column_config.NumberColumn("GST/TPS", format="$%.2f"),
                    "pst_amount": st.column_config.NumberColumn("PST/QST", format="$%.2f"),
                    "hst_amount": st.column_config.NumberColumn("HST/TVH", format="$%.2f"),
                },
                hide_index=True,
                num_rows="dynamic", # Allow adding/deleting expenses in a report
                key=f"editor_{selected_report_id}"
            )
            
            if st.button("Save Expense Changes"):
                with st.spinner("Saving..."):
                    # Logic to compare and update changed rows
                    # For simplicity, we can iterate and update all rows.
                    for index, row in edited_expenses_df.iterrows():
                        expense_id = row['id']
                        updates = {
                            "expense_date": str(row['expense_date']),
                            "vendor": row['vendor'],
                            "description": row['description'],
                            "amount": row['amount'],
                            "gst_amount": row.get('gst_amount'),
                            "pst_amount": row.get('pst_amount'),
                            "hst_amount": row.get('hst_amount'),
                            "category_id": category_map.get(row['category_name'])
                        }
                        su.update_expense_item(expense_id, updates)
                st.success("Changes saved successfully!")
                st.rerun()

        # --- Static View for Regular Users ---
        else:
            if not expenses_df.empty:
                for index, row in expenses_df.iterrows():
                    # ... (The existing static display logic from the last version) ...
                    # This section remains unchanged for users without editing privileges.
            else:
                st.info("No expense items found for this report.")

        # Export buttons are available to everyone
        st.markdown("---")
        st.subheader("Export This Full Report")
        # ... (The existing export logic remains unchanged) ...
