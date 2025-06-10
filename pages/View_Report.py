import streamlit as st
from utils import supabase_utils as su
import pandas as pd
import io
import re
import json

if not st.session_state.get("authentication_status"):
    st.warning("Please log in to access this page.")
    st.stop()

st.title("🗂️ View Submitted Expense Reports")
username = st.session_state.get("username")
user_id = su.get_user_id_by_username(username)

if not user_id:
    st.error("Could not identify user. Please log in again.")
    st.stop()

reports_df = su.get_reports_for_user(user_id)

if reports_df.empty:
    st.info("You have not submitted any expense reports yet.")
else:
    st.subheader("Your Reports Summary")
    report_options = {f"{row['report_name']} (Submitted: {pd.to_datetime(row['submission_date']).strftime('%Y-%m-%d')})": row['id'] for index, row in reports_df.iterrows()}
    report_options_list = ["-- Select a report --"] + list(report_options.keys())
    selected_report_display_name = st.selectbox("Select a report to view details:", options=report_options_list)

    if selected_report_display_name != "-- Select a report --":
        selected_report_id = report_options[selected_report_display_name]
        clean_report_name = re.sub(r'[^a-zA-Z0-9\s]', '', selected_report_display_name.split(' (')[0]).replace(' ', '_')

        st.subheader(f"Details for Report: {selected_report_display_name.split(' (')[0]}")
        
        expenses_df = su.get_expenses_for_report(selected_report_id)

        if not expenses_df.empty:
            # Loop through each expense (receipt) in the report and display its details
            for index, row in expenses_df.iterrows():
                st.markdown(f"#### Expense: {row.get('vendor', 'N/A')} - ${row.get('amount', 0):.2f}")
                
                exp_col1, exp_col2 = st.columns(2)
                with exp_col1:
                    st.write(f"**Date:** {row.get('expense_date', 'N/A')}")
                    st.write(f"**Description:** {row.get('description', 'N/A')}")
                with exp_col2:
                    st.write(f"**GST/TPS:** ${row.get('gst_amount', 0) or 0:.2f}")
                    st.write(f"**PST/QST:** ${row.get('pst_amount', 0) or 0:.2f}")
                    st.write(f"**HST/TVH:** ${row.get('hst_amount', 0) or 0:.2f}")

                # Create an expander for line items and the receipt image
                with st.expander("View Details (Line Items & Receipt)"):
                    line_items = []
                    if row.get('line_items'):
                        try:
                            # The data is stored as a JSON string, so we must load it
                            line_items = json.loads(row['line_items'])
                        except (json.JSONDecodeError, TypeError):
                            line_items = []
                    
                    if line_items and isinstance(line_items, list) and len(line_items) > 0:
                        st.write("**Line Items**")
                        line_items_df = pd.DataFrame(line_items)
                        st.dataframe(line_items_df)
                    else:
                        st.write("No line items were extracted for this expense.")

                    if row.get('receipt_path'):
                        st.write("**Receipt Image/PDF**")
                        receipt_url = su.get_receipt_public_url(row['receipt_path'])
                        if receipt_url:
                            # Display images directly, provide a link for PDFs
                            if row['receipt_path'].lower().endswith(('.png', '.jpg', '.jpeg')):
                                st.image(receipt_url)
                            else:
                                st.markdown(f"[{row['receipt_path'].split('/')[-1]}]({receipt_url})")
                    else:
                        st.write("No receipt was uploaded for this expense.")
                
                st.markdown("---")

            # Export buttons for the entire report's data
            st.subheader("Export This Full Report")
            export_df = expenses_df[[
                "expense_date", "vendor", "description", "amount", 
                "gst_amount", "pst_amount", "hst_amount"
            ]].copy()

            col1, col2 = st.columns(2)
            with col1:
                csv_data = export_df.to_csv(index=False).encode('utf-8')
                st.download_button(label="📥 Download as CSV", data=csv_data, file_name=f"{clean_report_name}.csv", mime="text/csv", use_container_width=True)
            with col2:
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    export_df.to_excel(writer, index=False, sheet_name='Expenses')
                excel_data = output.getvalue()
                st.download_button(label="📄 Download as Excel", data=excel_data, file_name=f"{clean_report_name}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
        else:
            st.info("No expense items found for this report.")
