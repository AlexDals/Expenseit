import streamlit as st
from utils import ocr_utils, supabase_utils as su
import pandas as pd
from datetime import date

if not st.session_state.get("authentication_status"):
    st.warning("Please login to access this page.")
    st.switch_page("streamlit_app.py")

st.title("📄 Create New Expense Report")
username = st.session_state.get("username")
user_id = su.get_user_id_by_username(username)

if not user_id:
    st.error("Could not identify user. Please log in again.")
    st.stop()

if 'current_report_items' not in st.session_state:
    st.session_state.current_report_items = []

report_name = st.text_input("Report Name/Purpose*", placeholder="e.g., Client Trip - June 2025")
st.subheader("Add Expense Item")

uploaded_receipt = st.file_uploader(
    "Upload Receipt (Image or PDF)", 
    type=["png", "jpg", "jpeg", "pdf"]
)

ocr_text_display = st.empty()
parsed_data = {}
receipt_path_for_db = None

if uploaded_receipt is not None:
    with st.spinner("Processing OCR and uploading receipt..."):
        ocr_raw_text = ocr_utils.extract_text_from_file(uploaded_receipt)
        
        ocr_text_display.text_area("Extracted OCR Text (Raw)", ocr_raw_text, height=200)
        parsed_data = ocr_utils.parse_ocr_text(ocr_raw_text)
        
        receipt_path_for_db = su.upload_receipt(uploaded_receipt, username)
        
        if receipt_path_for_db: 
            st.success("Receipt uploaded successfully!")
        else: 
            st.error("Failed to upload receipt.")
        st.info("OCR parsing is basic. Please verify the fields below.")
else:
    receipt_path_for_db = None

min_allowed_value = 0.01

with st.form("expense_item_form", clear_on_submit=True):
    col1, col2 = st.columns(2)
    with col1:
        # --- LOGIC CORRECTION FOR DATE HANDLING ---
        # 1. Try to convert the date string from OCR. errors='coerce' will turn failures into 'NaT'.
        parsed_timestamp = pd.to_datetime(parsed_data.get("date"), errors='coerce')

        # 2. Check if the result is 'NaT' (Not a Time). If so, default to today.
        if pd.isna(parsed_timestamp):
            initial_date = date.today()
        else:
            initial_date = parsed_timestamp.date()

        # 3. Pass the safe 'initial_date' to the widget.
        expense_date = st.date_input("Expense Date", value=initial_date)
        # --- END OF LOGIC CORRECTION ---

        vendor = st.text_input("Vendor Name", value=parsed_data.get("vendor", ""))
        
    with col2:
        ocr_amount = float(parsed_data.get("total_amount", 0.0))
        initial_value = max(min_allowed_value, ocr_amount)
        
        amount = st.number_input(
            "Amount",
            min_value=min_allowed_value,
            value=initial_value,
            format="%.2f"
        )
        
        description = st.text_area("Description")
        
    submitted_item = st.form_submit_button("Add Item to Report")

    if submitted_item and vendor and amount > 0:
        new_item = {
            "date": expense_date, "vendor": vendor, "description": description, "amount": amount,
            "receipt_path": receipt_path_for_db,
            "ocr_text": ocr_raw_text if uploaded_receipt and 'ocr_raw_text' in locals() else None
        }
        st.session_state.current_report_items.append(new_item)
        st.success(f"Added: {vendor} - ${amount:.2f}")

if st.session_state.current_report_items:
    st.markdown("---")
    st.subheader("Current Report Items")
    items_df = pd.DataFrame(st.session_state.current_report_items)
    st.dataframe(items_df[['date', 'vendor', 'description', 'amount']])
    total_report_amount = items_df['amount'].sum()
    st.metric("Total Report Amount", f"${total_report_amount:,.2f}")

    if st.button("Submit Entire Report", type="primary"):
        if not report_name:
            st.error("Please provide a Report Name before submitting.")
        else:
            with st.spinner("Submitting report..."):
                report_id = su.add_report(user_id, report_name, total_report_amount)
                if report_id:
                    for item in st.session_state.current_report_items:
                        su.add_expense_item(
                            report_id, item['date'], item['vendor'], item['description'], item['amount'],
                            item.get('receipt_path'), item.get('ocr_text')
                        )
                    st.success(f"Report '{report_name}' submitted successfully!")
                    st.session_state.current_report_items = []
                    st.rerun()
                else:
                    st.error("Failed to create report entry in database.")
