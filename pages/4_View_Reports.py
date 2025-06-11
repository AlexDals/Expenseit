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

# --- Display Reports and Details ---
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
        # We store the original dataframe in session state to compare against edits
        if 'original_expenses_df' not in st.session_state or st.session_state.get('loaded_report_id') != selected_report_id:
            st.session_state.original_expenses_df = su.get_expenses_for_report(selected_report_id)
            st.session_state.loaded_report_id = selected_report_id
        
        expenses_df = st.session_state.original_expenses_df

        # --- Approval & Editing Section (for Admins/Approvers) ---
        if user_role in ['admin', 'approver']:
            st.write(f"**Current Status:** `{selected_report_details['status']}`")
            
            if selected_report_details['status'] == 'Submitted':
                st.write("Actions:")
                bcol1, bcol2, bcol3 = st.columns([1, 1, 5])
                with bcol1:
                    if st.button("Approve", type="primary", use_container_width=True):
                        if su.update_report_status(selected_report_id, "Approved"):
                            st.success("Report Approved!")
                            st.rerun()
                with bcol2:
                    if st.button("Deny", use_container_width=True):
                        if su.update_report_status(selected_report_id, "Denied"):
                            st.warning("Report Denied.")
                            st.rerun()
            st.markdown("---")
            
            st.subheader("Edit Expense Details")
            st.info("You can edit the values directly in the table below. Click the 'Save Expense Changes' button when you are done.")
            
            categories = su.get_all_categories()
            category_names = [cat['name'] for cat in categories]
            category_map = {cat['name']: cat['id'] for cat in categories}
            
            edited_expenses_df = st.data_editor(
                expenses_df.copy(), # Use a copy to avoid mutation issues
                column_config={
                    "id": None, "report_id": None, "user_id": None, "receipt_path": None, 
                    "ocr_text": None, "line_items": None, "created_at": None, "category_id": None,
                    "expense_date": st.column_config.DateColumn("Date", required=True),
                    "vendor": "Vendor",
                    "description": "Purpose",
                    "amount": st.column_config.NumberColumn("Total", format="$%.2f", required=True),
                    "category_name": st.column_config.SelectboxColumn("Category", options=category_names, required=False),
                    "gst_amount": st.column_config.NumberColumn("GST/TPS", format="$%.2f"),
                    "pst_amount": st.column_config.NumberColumn("PST/QST", format="$%.2f"),
                    "hst_amount": st.column_config.NumberColumn("HST/TVH", format="$%.2f"),
                },
                hide_index=True,
                key=f"editor_{selected_report_id}"
            )
            
            if st.button("Save Expense Changes"):
                with st.spinner("Saving..."):
                    # Compare edited_df with the original expenses_df to find changes
                    changes = []
                    for index, edited_row in edited_expenses_df.iterrows():
                        original_row = expenses_df.loc[expenses_df['id'] == edited_row['id']]
                        if not original_row.empty:
                            if not original_row.iloc[0].equals(edited_row):
                                changes.append(edited_row)

                    all_success = True
                    for _, row in pd.DataFrame(changes).iterrows():
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
                        if not su.update_expense_item(expense_id, updates):
                            all_success = False
                
                if all_success:
                    st.success("Changes saved successfully!")
                    # Clear the cached dataframe for this report to force a refresh
                    st.session_state.original_expenses_df = None
                    st.rerun()
                else:
                    st.error("Failed to save one or more changes.")
        
        # --- Static View for Regular Users ---
        else:
            if not expenses_df.empty:
                for index, row in expenses_df.iterrows():
                    st.markdown(f"#### Expense: {row.get('vendor', 'N/A')} - ${row.get('amount', 0):.2f}")
                    exp_col1, exp_col2 = st.columns(2)
                    with exp_col1:
                        st.write(f"**Date:** {row.get('expense_date', 'N/A')}")
                        st.write(f"**Category:** `{row.get('category_name', 'N/A')}`")
                        st.write(f"**Purpose:** {row.get('description', 'N/A')}")
                    with exp_col2:
                        st.write(f"**GST/TPS:** ${row.get('gst_amount', 0) or 0:.2f}")
                        st.write(f"**PST/QST:** ${row.get('pst_amount', 0) or 0:.2f}")
                        st.write(f"**HST/TVH:** ${row.get('hst_amount', 0) or 0:.2f}")

                    with st.expander("View Details (Line Items & Receipt)"):
                        line_items = []
                        if row.get('line_items') and isinstance(row['line_items'], str):
                            try: line_items = json.loads(row['line_items'])
                            except (json.JSONDecodeError, TypeError): line_items = []
                        if line_items:
                            st.write("**Line Items**"); st.dataframe(pd.DataFrame(line_items))
                        else:
                            st.write("*No line items were extracted for this expense.*")
                        if row.get('receipt_path'):
                            st.write("**Receipt File**")
                            receipt_url = su.get_receipt_public_url(row['receipt_path'])
                            if receipt_url:
                                if row['receipt_path'].lower().endswith(('.png', '.jpg', '.jpeg')):
                                    st.image(receipt_url)
                                else:
                                    st.link_button("Download Receipt File", receipt_url)
                        else:
                            st.write("*No receipt was uploaded for this expense.*")
                    st.markdown("---")
            else:
                st.info("No expense items found for this report.")

        # --- Export Buttons Section ---
        st.subheader("Export This Full Report")
        export_df = expenses_df[["expense_date", "vendor", "description", "amount", "gst_amount", "pst_amount", "hst_amount"]].copy()
        btn_col1, btn_col2 = st.columns(2)
        with btn_col1:
            csv_data = export_df.to_csv(index=False).encode('utf-8')
            st.download_button(label="📥 Download as CSV", data=csv_data, file_name=f"{clean_report_name}.csv", mime="text/csv", use_container_width=True)
        with btn_col2:
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                export_df.to_excel(writer, index=False, sheet_name='Expenses')
            excel_data = output.getvalue()
            st.download_button(label="📄 Download as Excel", data=excel_data, file_name=f"{clean_report_name}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
