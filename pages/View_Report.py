import streamlit as st
from utils import supabase_utils as su
import pandas as pd

if not st.session_state.get("authentication_status"):
    st.warning("Please login to access this page.")
    st.switch_page("streamlit_app.py")

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
    st.dataframe(reports_df[['report_name', 'submission_date', 'total_amount']])
    report_options = {f"{row['report_name']} (Submitted: {pd.to_datetime(row['submission_date']).strftime('%Y-%m-%d')})": row['id'] for index, row in reports_df.iterrows()}
    selected_report_name = st.selectbox("Select a report to view details:", options=report_options.keys())

    if selected_report_name:
        selected_report_id = report_options[selected_report_name]
        st.subheader(f"Details for Report: {selected_report_name.split(' (')[0]}")
        
        expenses_df = su.get_expenses_for_report(selected_report_id)
        if not expenses_df.empty:
            expenses_df['receipt_image'] = expenses_df['receipt_path'].apply(su.get_receipt_public_url)
            st.dataframe(
                expenses_df,
                column_config={
                    "receipt_image": st.column_config.ImageColumn("Receipt", help="Receipt Image"),
                    "amount": st.column_config.NumberColumn("Amount", format="$%.2f"),
                },
                hide_index=True,
                column_order=("expense_date", "vendor", "description", "amount", "receipt_image")
            )
        else:
            st.info("No expense items found for this report.")
