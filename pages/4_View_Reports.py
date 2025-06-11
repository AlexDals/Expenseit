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

if not user_id:
    st.error("Could not identify user.")
    st.stop()

if 'denying_report_id' not in st.session_state:
    st.session_state.denying_report_id = None

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
        
        if st.session_state.denying_report_id and st.session_state.denying_report_id != selected_report_id:
            st.session_state.denying_report_id = None

        st.markdown("---")
        st.header(f"Details for: {selected_report_display_name.split(' (')[0]}")
        
        selected_report_details = reports_df[reports_df['id'] == selected_report_id].iloc[0]
        original_expenses_df = su.get_expenses_for_report(selected_report_id)

        if user_role in ['admin', 'approver']:
            st.write(f"**Current Status:** `{selected_report_details['status']}`")
            if selected_report_details['status'] == 'Denied' and pd.notna(selected_report_details.get('approver_comment')):
                st.error(f"**Reason for Denial:** {selected_report_details['approver_comment']}")

            if selected_report_details['status'] == 'Submitted':
                st.write("Actions:")
                bcol1, bcol2, bcol3 = st.columns([1, 1, 5])
                with bcol1:
                    if st.button("Approve", type="primary", use_container_width=True):
                        if su.update_report_status(selected_report_id, "Approved"):
                            st.success("Report Approved!"); st.session_state.denying_report_id = None; st.rerun()
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
                st.info("You can edit values directly in the table below.")
                
                expenses_to_edit = original_expenses_df.copy()
                categories = su.get_all_categories()
                category_names = [""] + [cat['name'] for cat in categories]
                category_map = {cat['name']: cat['id'] for cat in categories}
                
                expenses_to_edit['expense_date'] = pd.to_datetime(expenses_to_edit['expense_date'], errors='coerce')
                for col in ['amount', 'gst_amount', 'pst_amount', 'hst_amount']:
                    if col in expenses_to_edit.columns: expenses_to_edit[col] = pd.to_numeric(expenses_to_edit[col], errors='coerce').fillna(0)
                if 'category_name' in expenses_to_edit.columns:
                    expenses_to_edit['category_name'] = expenses_to_edit['category_name'].fillna("").astype(str)
                    valid_category_options = set(category_names)
                    expenses_to_edit['category_name'] = expenses_to_edit['category_name'].apply(lambda x: x if x in valid_category_options else "")

                edited_expenses_df = st.data_editor(expenses_to_edit, column_config={"id": None, "report_id": None, "user_id": None, "receipt_path": None, "ocr_text": None, "line_items": None, "created_at": None, "category_id": None, "expense_date": st.column_config.DateColumn("Date", required=True), "vendor": "Vendor", "description": "Purpose", "amount": st.column_config.NumberColumn("Total", format="$%.2f", required=True), "category_name": st.column_config.SelectboxColumn("Category", options=category_names, required=False), "gst_amount": st.column_config.NumberColumn("GST/TPS", format="$%.2f"), "pst_amount": st.column_config.NumberColumn("PST/QST", format="$%.2f"), "hst_amount": st.column_config.NumberColumn("HST/TVH", format="$%.2f")}, hide_index=True, key=f"editor_{selected_report_id}")
                
                if st.button("Save Expense Changes"):
                    with st.spinner("Saving..."):
                        all_success = True
                        for index, row in edited_expenses_df.iterrows():
                            expense_id = row.get('id')
                            if pd.notna(expense_id):
                                original_row_series = original_expenses_df[original_expenses_df['id'] == expense_id].iloc[0]
                                if not original_row_series.equals(row):
                                    updates = {"expense_date": str(row['expense_date'].date()), "vendor": row['vendor'], "description": row['description'], "amount": row['amount'], "gst_amount": row.get('gst_amount'), "pst_amount": row.get('pst_amount'), "hst_amount": row.get('hst_amount'), "category_id": category_map.get(row.get('category_name'))}
                                    if not su.update_expense_item(expense_id, updates): all_success = False
                        if all_success: st.success("Changes saved!"); st.rerun()
                        else: st.error("Failed to save one or more changes.")
        else: # Static view for regular users
            if not original_expenses_df.empty:
                for index, row in original_expenses_df.iterrows():
                    st.markdown(f"#### Expense: {row.get('vendor', 'N/A')} - ${row.get('amount', 0):.2f}")
                    # ... (rest of static view logic)
        
        # ... (Export buttons logic remains the same)
