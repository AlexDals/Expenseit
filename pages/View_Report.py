import streamlit as st
from utils import supabase_utils as su
import pandas as pd
import io # Required for in-memory Excel file

# --- CORRECTED AUTHENTICATION GUARD ---
if not st.session_state.get("authentication_status"):
    st.warning("Please log in to access this page.")
    st.stop() # Stop execution if not authenticated
# --- END OF CORRECTION ---

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
    # Format the options for the selectbox
    report_options = {f"{row['report_name']} (Submitted: {pd.to_datetime(row['submission_date']).strftime('%Y-%m-%d')})": row['id'] for index, row in reports_df.iterrows()}
    
    # Add a placeholder for the user to not have a report pre-selected
    report_options_list = ["-- Select a report --"] + list(report_options.keys())
    selected_report_display_name = st.selectbox("Select a report to view details:", options=report_options_list)

    # Check if a report has been selected (and it's not the placeholder)
    if selected_report_display_name != "-- Select a report --":
        selected_report_id = report_options[selected_report_display_name]
        
        # Extract a clean report name for filenames
        clean_report_name = re.sub(r'[^a-zA-Z0-9\s]', '', selected_report_display_name.split(' (')[0]).replace(' ', '_')

        st.subheader(f"Details for Report: {selected_report_display_name.split(' (')[0]}")
        
        expenses_df = su.get_expenses_for_report(selected_report_id)

        if not expenses_df.empty:
            expenses_df['receipt_image'] = expenses_df['receipt_path'].apply(su.get_receipt_public_url)
            
            display_cols = [
                "expense_date", "vendor", "description", 
                "gst_amount", "pst_amount", "hst_amount", 
                "amount", "receipt_image"
            ]
            
            st.dataframe(
                expenses_df,
                column_config={
                    "receipt_image": st.column_config.ImageColumn("Receipt"),
                    "amount": st.column_config.NumberColumn("Total", format="$%.2f"),
                    "gst_amount": st.column_config.NumberColumn("GST/TPS", format="$%.2f"),
                    "pst_amount": st.column_config.NumberColumn("PST/QST", format="$%.2f"),
                    "hst_amount": st.column_config.NumberColumn("HST/TVH", format="$%.2f"),
                },
                hide_index=True,
                column_order=display_cols
            )

            # --- NEW: EXPORT BUTTONS SECTION ---
            st.markdown("---")
            st.subheader("Export This Report")

            # Prepare data for export (we don't need all the raw columns)
            export_df = expenses_df[[
                "expense_date", "vendor", "description", "amount", 
                "gst_amount", "pst_amount", "hst_amount"
            ]].copy()

            col1, col2 = st.columns(2)

            with col1:
                # --- CSV Download ---
                csv_data = export_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Download as CSV",
                    data=csv_data,
                    file_name=f"{clean_report_name}.csv",
                    mime="text/csv",
                    use_container_width=True
                )

            with col2:
                # --- Excel Download ---
                # Write to an in-memory buffer
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    export_df.to_excel(writer, index=False, sheet_name='Expenses')
                excel_data = output.getvalue()

                st.download_button(
                    label="📄 Download as Excel",
                    data=excel_data,
                    file_name=f"{clean_report_name}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            # --- END OF NEW SECTION ---

        else:
            st.info("No expense items found for this report.")
