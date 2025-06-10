import streamlit as st
from utils import ocr_utils, supabase_utils as su
import pandas as pd
from datetime import date

if not st.session_state.get("authentication_status"):
    st.warning("Please log in to access this page.")
    st.stop()

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

parsed_data = {}
receipt_path_for_db = None

if uploaded_receipt is not None:
    with st.spinner("Processing OCR and uploading receipt..."):
        raw_text, parsed_data = ocr_utils.extract_and_parse_file(uploaded_receipt)

        with st.expander("View Raw Extracted Text"):
            st.text_area("OCR Output", raw_text, height=300)

        if "error" in parsed_data:
            st.error(parsed_data["error"])
            parsed_data = {} 
        else:
            st.success("OCR processing complete. Please verify the extracted values.")
        
        receipt_path_for_db = su.upload_receipt(uploaded_receipt, username)
        if receipt_path_for_db: st.success("Receipt uploaded successfully!")
        else: st.error("Failed to upload receipt.")
else:
    parsed_data = {"date": None, "vendor": "", "total_amount": 0.0, "gst_amount": 0.0, "pst_amount": 0.0, "hst_amount": 0.0}

min_allowed_value = 0.01

with st.form("expense_item_form", clear_on_submit=True):
    col1, col2 = st.columns(2)
    with col1:
        parsed_timestamp = pd.to_datetime(parsed_data.get("date"), errors='coerce')
        initial_date = date.today() if pd.isna(parsed_timestamp) else parsed_timestamp.date()
        expense_date = st.date_input("Expense Date", value=initial_date)
        vendor = st.text_input("Vendor Name", value=parsed_data.get("vendor", ""))
        description = st.text_area("Description")
        
    with col2:
        ocr_amount = float(parsed_data.get("total_amount", 0.0))
        initial_value = max(min_allowed_value, ocr_amount)
        amount = st.number_input("Amount (Total)", min_value=min_allowed_value, value=initial_value, format="%.2f")

        st.markdown("###### Taxes (Editable)")
        tax_col1, tax_col2, tax_col3 = st.columns(3)
        with tax_col1:
            gst_amount = st.number_input("GST/TPS", min_value=0.0, value=float(parsed_data.get("gst_amount", 0.0)), format="%.2f")
        with tax_col2:
            pst_amount = st.number_input("PST/QST", min_value=0.0, value=float(parsed_data.get("pst_amount", 0.0)), format="%.2f")
        with tax_col3:
            hst_amount = st.number_input("HST/TVH", min_value=0.0, value=float(parsed_data.get("hst_amount", 0.0)), format="%.2f")
        
    submitted_item = st.form_submit_button("Add Item to Report")

    if submitted_item and vendor and amount > 0:
        new_item = {
            "date": expense_date, "vendor": vendor, "description": description, "amount": amount,
            "receipt_path": receipt_path_for_db,
            "ocr_text": raw_text if uploaded_receipt else "N/A",
            "gst_amount": gst_amount, "pst_amount": pst_amount, "hst_amount": hst_amount
        }
        st.session_state.current_report_items.append(new_item)
        st.success(f"Added: {vendor} - ${amount:.2f}")

if st.session_state.current_report_items:
    st.markdown("---")
    st.subheader("Current Report Items")
    display_cols = ['date', 'vendor', 'description', 'gst_amount', 'pst_amount', 'hst_amount', 'amount']
    items_df = pd.DataFrame(st.session_state.current_report_items)
    st.dataframe(items_df[display_cols])
    total_report_amount = items_df['amount'].sum()
    st.metric("Total Report Amount", f"${total_report_amount:,.2f}")

    # --- NEW, SAFER SUBMISSION LOGIC ---
    if st.button("Submit Entire Report", type="primary"):
        if not report_name:
            st.error("Please provide a Report Name before submitting.")
        else:
            with st.spinner("Submitting report..."):
                report_id = su.add_report(user_id, report_name, total_report_amount)
                
                if report_id:
                    all_items_saved = True # Assume success at first
                    for item in st.session_state.current_report_items:
                        # The function now returns True or False
                        success = su.add_expense_item(
                            report_id, item['date'], item['vendor'], item['description'], item['amount'],
                            item.get('receipt_path'), item.get('ocr_text'),
                            item.get('gst_amount'), item.get('pst_amount'), item.get('hst_amount')
                        )
                        if not success:
                            all_items_saved = False # Mark as failed
                            break # Stop processing further items
                    
                    # Only show success and clear the list if ALL items were saved
                    if all_items_saved:
                        st.success(f"Report '{report_name}' submitted successfully!")
                        st.balloons()
                        st.session_state.current_report_items = []
                        st.rerun()
                    else:
                        st.error("Critical Error: The report header was saved, but saving one or more expense items failed. Your entered items have NOT been cleared. Please review any errors above and try submitting again.")

                else:
                    st.error("Critical Error: Failed to create the main report entry in the database. Please try again.")
