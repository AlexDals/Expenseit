import streamlit as st
from utils import ocr_utils, supabase_utils as su
import pandas as pd
from datetime import date

# ... (all the code at the top of the file remains the same) ...

ocr_text_display = st.empty()
parsed_data = {}
receipt_path_for_db = None

if uploaded_receipt is not None:
    with st.spinner("Processing OCR and uploading receipt..."):
        # --- THIS IS THE MAIN CHANGE ---
        # Call the new, single pipeline function
        parsed_data = ocr_utils.extract_and_parse_file(uploaded_receipt)

        # Check for and display any errors from the OCR process
        if "error" in parsed_data:
            st.error(parsed_data["error"])
            # Clear parsed_data so the form doesn't use old/bad values
            parsed_data = {} 
        else:
            st.success("OCR processing complete. Please verify the extracted values.")
        # --- END OF CHANGE ---
        
        # We no longer display the raw text as it's not very useful
        # ocr_text_display.text_area(...) # This line can be removed

        receipt_path_for_db = su.upload_receipt(uploaded_receipt, username)
        
        if receipt_path_for_db: 
            st.success("Receipt uploaded successfully!")
        else: 
            st.error("Failed to upload receipt.")
else:
    # Initialize with default structure if no file is uploaded
    parsed_data = {"date": None, "vendor": "", "total_amount": 0.0, "gst_amount": 0.0, "pst_amount": 0.0, "hst_amount": 0.0}

# ... (the rest of the file, including the st.form, remains the same) ...
