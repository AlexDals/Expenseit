# File: pages/3_New_Report.py

import streamlit as st
import uuid
import datetime

# Dynamically import your OCR utils module
from utils import ocr_utils
from utils.supabase_utils import init_connection

st.set_page_config(page_title="New Report", layout="wide")
st.title("New Report")

# — Make sure the user is logged in:
username = st.session_state.get("username")
if not username:
    st.error("You must be logged in to submit a report.")
    st.stop()

# — File uploader
uploaded = st.file_uploader(
    "Upload a receipt (PNG, JPG, PDF)",
    type=["png", "jpg", "jpeg", "pdf"]
)
if not uploaded:
    st.info("Please upload a receipt to get started.")
    st.stop()

# — Process button
if st.button("Process Receipt"):
    # 1) Figure out which OCR function you actually have
    if hasattr(ocr_utils, "extract_text_from_image"):
        do_ocr = ocr_utils.extract_text_from_image
    elif hasattr(ocr_utils, "perform_ocr"):
        do_ocr = ocr_utils.perform_ocr
    elif hasattr(ocr_utils, "ocr_image"):
        do_ocr = ocr_utils.ocr_image
    else:
        st.error(
            "No OCR function found in utils/ocr_utils.py.\n"
            "Please define one of: extract_text_from_image, perform_ocr, or ocr_image."
        )
        st.stop()

    # 2) Run OCR
    with st.spinner("Running OCR..."):
        try:
            ocr_text = do_ocr(uploaded)
        except Exception as e:
            st.error(f"OCR failed: {e}")
            st.stop()

    st.markdown("**Extracted text:**")
    st.text_area("", value=ocr_text, height=200)

    # 3) Upload receipt file to Supabase Storage
    supabase = init_connection()
