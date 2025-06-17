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
user_id = st.session_state.get("user_id")
if not user_id:
    st.error("User profile not found in session."); st.stop()
if 'denying_report_id' not in st.session_state:
    st.session_state.denying_report_id = None

reports_df = pd.DataFrame()
if user_role == 'user':
    st.subheader("Your Submitted Reports"); reports_df = su.get_reports_for_user(user_id)
elif user_role == 'approver':
    st.subheader("Reports Awaiting Your Approval"); reports_df = su.get_reports_for_approver(user_id)
elif user_role == 'admin':
    st.subheader("All Company Reports"); reports_df = su.get_all_reports()

if reports_df.empty:
    st.info("No reports found for your view.")
else:
    if 'user' in reports_df.columns:
        reports_df['submitter_name'] = reports_df['user'].apply(lambda x: x.get('name') if isinstance(x, dict) else 'N/A')
        reports_df['submitter_name'] = reports_df['submitter_name'].fillna('Unknown User')
        reports_df['display_name'] = reports_df['report_name'] + " by " + reports_df['submitter_name'] + " (Status: " + reports_df['status'] + ")"
    else:
        reports_df['display_name'] = reports_df['report_name'] + " (Status: " + reports_df['status'] + ")"
    
    id_to_display_name_map = {row['id']: row['display_name'] for index, row in reports_df.iterrows()}
    report_id_options = ["-- Select a report --"] + list(id_to_display_name_map.keys())
    selected_report_id = st.selectbox("Select a report:", options=report_id_options, format_func=lambda rid: id_to_display_name_map.get(rid, "-- Select a report --"))

    if selected_report_id != "-- Select a report --":
        if st.session_state.denying_report_id and st.session_state.denying_report_id != selected_report_id:
            st.session_state.denying_report_id = None
        st.markdown("---")
        st.header(f"Details for: {id_to_display_name_map[selected_report_id].split(' (')[0]}")
        selected_report_details = reports_df[reports_df['id'] == selected_report_id].iloc[0]
        original_expenses_df = su.get_expenses_for_report(selected_report_id)

        if user_role in ['admin', 'approver']:
            # ... (Approval buttons and denial form logic) ...
            if not original_expenses_df.empty:
                st.subheader("Edit Expense Details")
                # ... (Data editor logic) ...
        else: # Static View for Regular Users
            if not original_expenses_df.empty:
                for index, row in original_expenses_df.iterrows():
                    # ... (Static display logic) ...
        
        if not original_expenses_df.empty:
            st.subheader("Export This Full Report")
            clean_report_name = re.sub(r'[^a-zA-Z0-9\s]', '', id_to_display_name_map[selected_report_id].split(' (')[0]).replace(' ', '_')
            desired_export_columns = ["expense_date", "vendor", "description", "amount", "gst_amount", "pst_amount", "hst_amount", "category_name"]
            available_columns_for_export = [col for col in desired_export_columns if col in original_expenses_df.columns]
            
            if available_columns_for_export:
                export_df = original_expenses_df[available_columns_for_export].copy()
                btn_col1, btn_col2, btn_col3 = st.columns(3)
                with btn_col1:
                    csv_data = export_df.to_csv(index=False).encode('utf-8')
                    st.download_button(label="📥 Download as CSV", data=csv_data, file_name=f"{clean_report_name}.csv", mime="text/csv", use_container_width=True)
                with btn_col2:
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        export_df.to_excel(writer, index=False, sheet_name='Expenses')
                    excel_data = output.getvalue()
                    st.download_button(label="📄 Download as Excel", data=excel_data, file_name=f"{clean_report_name}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
                with btn_col3:
                    submitter_name = selected_report_details.get('submitter_name', 'N/A')
                    xml_data = su.generate_report_xml(selected_report_details, original_expenses_df, submitter_name)
                    st.download_button(label="💿 Download as XML", data=xml_data, file_name=f"{clean_report_name}.xml", mime="application/xml", use_container_width=True)
