# File: pages/3_New_Report.py

import streamlit as st
import uuid
import datetime
from utils.ocr_utils import extract_text_from_image  # adjust to your actual OCR function
from utils.supabase_utils import init_connection

st.set_page_config(page_title="New Report", layout="wide")
st.title("New Report")

# Ensure the user is logged in and we have their username
username = st.session_state.get("username")
if not username:
    st.error("You must be logged in to submit a report.")
    st.stop()

# Receipt uploader
uploaded = st.file_uploader(
    "Upload a receipt (PNG, JPG, PDF)", 
    type=["png", "jpg", "jpeg", "pdf"]
)
if not uploaded:
    st.info("Please upload a receipt to get started.")
    st.stop()

if st.button("Process Receipt"):
    supabase = init_connection()

    # 1) Run OCR
    with st.spinner("Running OCR..."):
        try:
            ocr_text = extract_text_from_image(uploaded)
        except Exception as e:
            st.error(f"OCR failed: {e}")
            st.stop()
    st.write("**Extracted text:**")
    st.text_area("", value=ocr_text, height=200)

    # 2) Upload receipt to Supabase Storage
    with st.spinner("Uploading receipt to storage..."):
        # Generate a unique filename
        ext = uploaded.name.split(".")[-1]
        unique_id = str(uuid.uuid4())
        storage_path = f"{username}/{unique_id}.{ext}"

        # Supabase expects raw bytes
        file_bytes = uploaded.getvalue()
        storage_resp = (
            supabase
            .storage
            .from_("receipts")
            .upload(storage_path, file_bytes)
        )

        # Check for upload errors
        if hasattr(storage_resp, "error") and storage_resp.error:
            st.error(f"Storage upload error: {storage_resp.error.message}")
            st.stop()

    st.success("Receipt uploaded successfully!")

    # 3) Persist the report record in your DB
    with st.spinner("Saving report record..."):
        report_record = {
            "username": username,
            "receipt_path": storage_path,
            "ocr_text": ocr_text,
            "created_at": datetime.datetime.utcnow().isoformat(),
        }
        db_resp = supabase.table("reports").insert(report_record).execute()
        if hasattr(db_resp, "error") and db_resp.error:
            st.error(f"Database error: {db_resp.error.message}")
            st.stop()

    st.success("New expense report created!")
    st.balloons()
