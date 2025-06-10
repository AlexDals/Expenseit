import streamlit as st
from utils import ocr_utils, supabase_utils as su
import pandas as pd
from datetime import date

# --- AUTHENTICATION GUARD ---
if not st.session_state.get("authentication_status"):
    st.warning("Please log in to access this page.")
    st.stop()

# --- PAGE SETUP ---
st.title("📄 Create New Expense Report")
username = st.session_state.get("username")
user_id = su.get_user_id_by_username(username)

if not user_id:
    st.error("Could not identify user. Please log in again.")
    st.stop()

if 'current_report_items' not in st.session_state:
    st.session_state.current_report_items = []

# --- MAIN UI ---
report_name = st.text_input("Report Name/Purpose*", placeholder="e.g., Client Trip - June 2025")
st.subheader("Add Expense Item")

uploaded_receipt = st.file_uploader(
    "Upload Receipt (Image or PDF)",
    type=["png", "jpg", "jpeg", "pdf"]
)

# Initialize variables
parsed_data = {}
receipt_path_for_db = None
raw_text = ""

if uploaded_receipt is not None:
    with st.spinner("Processing OCR and uploading receipt..."):
        raw_text, parsed_data = ocr_utils.extract_and_parse_file(uploaded_receipt)

        if "error" in parsed_data:
            st.error(parsed_data["error"])
            parsed_data = {}
        else:
            st.success("OCR processing complete. Please verify the
