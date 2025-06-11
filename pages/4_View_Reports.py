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
    selected_report_display_name = st.selectbox("Select a report to view its details:", options=report_options_list)

    if selected_report_display_name != "-- Select a report --":
        selected_report_id = report_options[selected_report_display_name]
        st.markdown("---")
        st.header(f"Details for: {selected_report_display_name.split(' (')[0]}")
        
        selected_report_details = reports_df[reports_df['id'] == selected_report_id].iloc[0]
        original_expenses_df = su.get_expenses_for_report(selected_report_id)

        # --- Approval Section (for Admins/Approvers) ---
        if user_role in ['admin', 'approver']:
            st.write(f"**Current Status:** `{selected_report_details['status']}`")
            if selected_report_details['status'] == 'Submitted':
                st.write("Actions:")
                bcol1, bcol2, bcol3 = st.columns([1, 1, 5])
                if bcol1.button("Approve", type="primary", use_container_width=True):
                    if su.update_report_status(selected_report_id, "Approved"): st.success("Report Approved!"); st.rerun()
                if bcol2.button("Deny", use_container_width=True):
                    if su.update_report_status(selected_report_id, "Denied"): st.warning("Report Denied."); st.rerun()
            st.markdown("---")
        
        if not original_expenses_df.empty:
            # --- Editing and Static View Section ---
            if user_role in ['admin', 'approver']:
                st.subheader("Edit Expense Details")
                st.info("You can edit the values directly in the table below. Click the 'Save Expense Changes' button when you are done.")
                
                # --- NEW: Prepare DataFrame for Data Editor ---
                expenses_to_edit = original_expenses_df.copy()
                categories = su.get_all_categories()
                category_names = [""] + [cat['name'] for cat in categories]
                category_map = {cat['name']: cat['id'] for cat in categories}
                
                # 1. Convert date column to datetime objects
                expenses_to_edit['expense_date'] = pd.to_datetime(expenses_to_edit['expense_date'], errors='coerce')
                
                # 2. Fill missing numeric values with 0
                for col in ['amount', 'gst_amount', 'pst_amount', 'hst_amount']:
                    if col in expenses_to_edit.columns:
                        expenses_to_edit[col] = pd.to_numeric(expenses_to_edit[col], errors='coerce').fillna(0)

                # 3. Ensure category column has a valid default for the selectbox
                if 'category_name' in expenses_to_edit.columns:
                    expenses_to_edit['category_name'] = expenses_to_edit['category_name'].fillna("").astype(str)
                    # Ensure every category in the dataframe is a valid option
                    valid_category_options = set(category_names)
                    expenses_to_edit['category_name'] = expenses_to_edit['category_name'].apply(lambda x: x if x in valid_category_options else "")
                # --- END OF PREPARATION ---

                edited_expenses_df = st.data_editor(
                    expenses_to_edit,
                    column_config={
                        "id": None, "report_id": None, "user_id": None, "receipt_path": None, "ocr_text": None, 
                        "line_items": None, "created_at": None, "category_id": None,
                        "expense_date": st.column_config.DateColumn("Date", required=True),
                        "vendor": "Vendor", "description": "Purpose",
                        "amount": st.column_config.NumberColumn("Total", format="$%.2f", required=True),
                        "category_name": st.column_config.SelectboxColumn("Category", options=category_names, required=False),
                        "gst_amount": st.column_config.NumberColumn("GST/TPS", format="$%.2f"),
                        "pst_amount": st.column_config.NumberColumn("PST/QST", format="$%.2f"),
                        "hst_amount": st.column_config.NumberColumn("HST/TVH", format="$%.2f"),
                    },
                    hide_index=True, num_rows="dynamic", key=f"editor_{selected_report_id}"
                )
                
                if st.button("Save Expense Changes"):
                    with st.spinner("Saving..."):
                        changes_df = pd.concat([original_expenses_df, edited_expenses_df]).drop_duplicates(keep=False)
                        all_success = True
                        for index, row in changes_df.iterrows():
                            expense_id = row['id']
                            updates = row.to_dict()
                            # Convert category name back to ID for saving
                            updates['category_id'] = category_map.get(row.get('category_name'))
                            # Remove non-db columns
                            updates.pop('category_name', None); updates.pop('user', None)
                            
                            if not su.update_expense_item(expense_id, updates):
                                all_success = False
                    if all_success: st.success("Changes saved!"); st.rerun()
                    else: st.error("Failed to save one or more changes.")

            # Static View for Regular Users
            else:
                for index, row in original_expenses_df.iterrows():
                    # ... (The existing static display logic from the last version) ...
                    st.markdown(f"#### Expense: {row.get('vendor', 'N/A')} - ${row.get('amount', 0):.2f}")
                    # ... etc
        else:
            st.info("No expense items found for this report.")

        # --- Export Buttons Section ---
        st.markdown("---")
        st.subheader("Export This Full Report")
        # ... (The existing export logic remains unchanged) ...
