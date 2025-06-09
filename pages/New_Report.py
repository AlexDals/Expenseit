import streamlit as st
from utils import ocr_utils, db_utils
import pandas as pd
from datetime import date

# --- Authentication check ---
if 'authentication_status' not in st.session_state or not st.session_state['authentication_status']:
    st.warning("Please login to access this page.")
    st.switch_page("streamlit_app.py") # Redirect to login

st.title("📄 Create New Expense Report")

# Ensure username is available from session state after login
username = st.session_state.get("username")
if not username:
    st.error("User not identified. Please log in again.")
    st.stop()

# --- Initialize Session State for Report Items ---
if 'current_report_items' not in st.session_state:
    st.session_state.current_report_items = []

report_name = st.text_input("Report Name/Purpose", placeholder="e.g., Client Trip Q2")
st.subheader("Add Expense Item")
uploaded_receipt = st.file_uploader("Upload Receipt Image (Optional)", type=["png", "jpg", "jpeg"])
ocr_text_display = st.empty()
parsed_data = {}
image_bytes_for_db = None # Define outside to ensure it's available for form

if uploaded_receipt is not None:
    image_bytes_for_db = uploaded_receipt.getvalue() # Store bytes for DB
    with st.spinner("Processing OCR..."):
        ocr_raw_text = ocr_utils.extract_text_from_image(image_bytes_for_db)
        ocr_text_display.text_area("Extracted OCR Text (Raw)", ocr_raw_text, height=150)
        parsed_data = ocr_utils.parse_ocr_text(ocr_raw_text)
        st.info("OCR parsing is basic. Please verify and correct the fields below.")

with st.form("expense_item_form", clear_on_submit=True):
    col1, col2 = st.columns(2)
    with col1:
        expense_date = st.date_input("Expense Date", value=pd.to_datetime(parsed_data.get("date", date.today()), errors='coerce'))
        vendor = st.text_input("Vendor Name", value=parsed_data.get("vendor", ""))
    with col2:
        amount = st.number_input("Amount", min_value=0.0, value=float(parsed_data.get("total_amount", 0.0)), format="%.2f")
        description = st.text_area("Description/Purpose of Expense", height=50)
    submitted_item = st.form_submit_button("Add Item to Report")

    if submitted_item:
        if not vendor or not amount > 0 or not expense_date:
            st.warning("Please fill in at least Date, Vendor, and Amount.")
        else:
            new_item = {
                "date": expense_date, "vendor": vendor, "description": description, "amount": amount,
                "receipt_image_bytes": image_bytes_for_db if uploaded_receipt else None, # Use stored bytes
                "ocr_text": ocr_raw_text if uploaded_receipt and 'ocr_raw_text' in locals() else None
            }
            st.session_state.current_report_items.append(new_item)
            st.success(f"Added: {vendor} - ${amount:.2f}")
            ocr_text_display.empty() # Clear previous OCR text
            # uploaded_receipt is not directly clearable this way, user has to remove it.

if st.session_state.current_report_items:
    st.subheader("Current Report Items")
    items_df = pd.DataFrame(st.session_state.current_report_items)
    st.dataframe(items_df[['date', 'vendor', 'description', 'amount']])
    total_report_amount = items_df['amount'].sum()
    st.metric("Total Report Amount", f"${total_report_amount:,.2f}")

    if st.button("Submit Entire Report"):
        if not report_name:
            st.error("Please provide a Report Name before submitting.")
        else:
            try:
                report_id = db_utils.add_report(username, report_name, total_report_amount)
                for item in st.session_state.current_report_items:
                    db_utils.add_expense_item(
                        report_id, item['date'], item['vendor'], item['description'], item['amount'],
                        item.get('receipt_image_bytes'), item.get('ocr_text')
                    )
                st.success(f"Report '{report_name}' submitted successfully with ID: {report_id}!")
                st.session_state.current_report_items = []
                st.rerun()
            except Exception as e:
                st.error(f"Error submitting report: {e}")
else:
    st.info("Add items to your report using the form above.")
