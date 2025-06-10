import streamlit as st
from utils import ocr_utils, supabase_utils as su
import pandas as pd
from datetime import date

if not st.session_state.get("authentication_status"):
    st.warning("Please log in to access this page.")
    st.stop()

st.title("📄 Create New Expense Report")
# ... (user info setup code) ...
# ... (session state setup code) ...

report_name = st.text_input("Report Name/Purpose*", placeholder="e.g., Client Trip - June 2025")
st.subheader("Add Expense Item")
uploaded_receipt = st.file_uploader("Upload Receipt (Image or PDF)", type=["png", "jpg", "jpeg", "pdf"])

parsed_data, raw_text, receipt_path_for_db = {}, "", None

if uploaded_receipt:
    with st.spinner("Processing OCR and uploading receipt..."):
        raw_text, parsed_data = ocr_utils.extract_and_parse_file(uploaded_receipt)
        with st.expander("View Raw Extracted Text"):
            st.text_area("OCR Output", raw_text, height=300)
        if "error" in parsed_data:
            st.error(parsed_data["error"]); parsed_data = {}
        else:
            st.success("OCR processing complete. Please verify the extracted values.")
        receipt_path_for_db = su.upload_receipt(uploaded_receipt, username)
        if receipt_path_for_db: st.success("Receipt uploaded successfully!")
        else: st.error("Failed to upload receipt.")
else:
    parsed_data = {"date": None, "vendor": "", "total_amount": 0.0, "gst_amount": 0.0, "pst_amount": 0.0, "hst_amount": 0.0, "line_items": []}

if parsed_data.get("line_items"):
    st.markdown("---"); st.subheader("Extracted Line Items")
    st.dataframe(pd.DataFrame(parsed_data["line_items"])); st.markdown("---")

min_allowed_value = 0.01
with st.form("expense_item_form", clear_on_submit=True):
    # ... (form layout code, col1, col2, etc. - no changes here) ...
    # ... (date, vendor, description, amount, taxes inputs - no changes here) ...
    submitted_item = st.form_submit_button("Add Item to Report")
    if submitted_item and vendor and amount > 0:
        new_item = {
            "date": expense_date, "vendor": vendor, "description": description, "amount": amount,
            "receipt_path": receipt_path_for_db, "ocr_text": raw_text if uploaded_receipt else "N/A",
            "gst_amount": gst_amount, "pst_amount": pst_amount, "hst_amount": hst_amount,
            "line_items": parsed_data.get("line_items", []) # Ensure line_items are added
        }
        st.session_state.current_report_items.append(new_item)
        st.success(f"Added: {vendor} - ${amount:.2f}")

if st.session_state.current_report_items:
    # ... (Display current report items dataframe - no changes here) ...
    if st.button("Submit Entire Report", type="primary"):
        if not report_name: st.error("Please provide a Report Name before submitting.")
        else:
            with st.spinner("Submitting report..."):
                report_id = su.add_report(user_id, report_name, total_report_amount)
                if report_id:
                    all_items_saved = True
                    for item in st.session_state.current_report_items:
                        success = su.add_expense_item( # Pass all arguments including line_items
                            report_id, item['date'], item['vendor'], item['description'], item['amount'],
                            item.get('receipt_path'), item.get('ocr_text'),
                            item.get('gst_amount'), item.get('pst_amount'), item.get('hst_amount'),
                            item.get('line_items')
                        )
                        if not success: all_items_saved = False; break
                    if all_items_saved:
                        # ... (success message and cleanup) ...
                    else:
                        st.error("Critical Error: Failed to save one or more items...")
                else:
                    st.error("Critical Error: Failed to create main report entry...")
