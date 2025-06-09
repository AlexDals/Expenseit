import streamlit as st
from utils import db_utils
import pandas as pd

if 'authentication_status' not in st.session_state or not st.session_state['authentication_status']:
    st.warning("Please login to access this page.")
    st.switch_page("streamlit_app.py") # Redirect to login

st.title("🗂️ View Submitted Expense Reports")

username = st.session_state.get("username")
if not username:
    st.error("User not identified. Please log in again.")
    st.stop()

reports_df = db_utils.get_reports_for_user(username)

if reports_df.empty:
    st.info("You have not submitted any expense reports yet.")
else:
    st.subheader("Your Reports Summary")
    st.dataframe(reports_df[['report_name', 'submission_date', 'total_amount']])
    report_ids = reports_df['id'].tolist()
    report_names = reports_df['report_name'].tolist()
    options = [f"{name} (ID: {id})" for name, id in zip(report_names, report_ids)]
    selected_report_option = st.selectbox("Select a report to view details:", options, index=None, placeholder="Choose a report")

    if selected_report_option:
        selected_report_id = int(selected_report_option.split("(ID: ")[1][:-1])
        st.subheader(f"Details for Report: {selected_report_option.split(' (ID:')[0]}")
        expenses_df = db_utils.get_expenses_for_report(selected_report_id)
        if expenses_df.empty:
            st.info("No expense items found for this report.")
        else:
            st.dataframe(expenses_df[['expense_date', 'vendor', 'description', 'amount', 'ocr_text']])

    st.markdown("---")
    st.subheader("Export All Your Expense Data")
    all_user_expenses_df = db_utils.get_all_expenses_for_user_for_export(username)
    if not all_user_expenses_df.empty:
        csv = all_user_expenses_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Download All Expenses as CSV",
            data=csv,
            file_name=f'{username}_all_expense_reports.csv',
            mime='text/csv',
        )
    else:
        st.info("No data available to export.")
