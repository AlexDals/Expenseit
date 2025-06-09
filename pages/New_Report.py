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
uploaded_receipt = st.file_uploader("Upload Receipt Image (Optional)", type=["png", "jpg", "jpeg"])
ocr_text_display = st.empty()
parsed_data = {}
receipt_path_for_db = None

if uploaded_receipt is not None:
    image_bytes = uploaded_receipt.getvalue()
    with st.spinner("Processing OCR and uploading receipt..."):
        ocr_raw_text = ocr_utils.extract_text_from_image(image_bytes)
        ocr_text_display.text_area("Extracted OCR Text (Raw)", ocr_raw_text, height=150)
        parsed_data = ocr_utils.parse_ocr_text(ocr_raw_text)
        receipt_path_for_db = su.upload_receipt(image_bytes, username)
        if receipt_path_for_db: st.success("Receipt uploaded successfully!")
        else: st.error("Failed to upload receipt.")
        st.info("OCR parsing is basic. Please verify the fields below.")
else:
    receipt_path_for_db = None

# --- Form for Expense Item Details ---
with st.form("expense_item_form", clear_on_submit=True):
    col1, col2 = st.columns(2)
    with col1:
        expense_date = st.date_input("Expense Date", value=pd.to_datetime(parsed_data.get("date", date.today()), errors='coerce'))
        vendor = st.text_input("Vendor Name", value=parsed_data.get("vendor", ""))
    with col2:
        min_allowed
