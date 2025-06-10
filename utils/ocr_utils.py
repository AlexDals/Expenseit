import pytesseract
from PIL import Image
import io
import re
import fitz  # PyMuPDF
import cv2  # OpenCV
import numpy as np
from google.cloud import vision
import streamlit as st

# --- GOOGLE VISION API AND IMAGE PREPROCESSING (No changes) ---
@st.cache_resource
def get_vision_client():
    try:
        credentials_dict = dict(st.secrets.google_credentials)
        client = vision.ImageAnnotatorClient.from_service_account_info(credentials_dict)
        return client
    except Exception as e:
        st.error(f"Could not initialize Google Vision API client: {e}. Please check your Streamlit secrets.")
        st.stop()

def extract_text_from_file(uploaded_file):
    """Extracts text from file using OCR."""
    client = get_vision_client()
    file_bytes = uploaded_file.getvalue()
    try:
        if uploaded_file.type == "application/pdf":
            full_text = ""
            with fitz.open(stream=file_bytes, filetype="pdf") as doc:
                for page in doc:
                    pix = page.get_pixmap(dpi=300)
                    image = vision.Image(content=pix.tobytes("png"))
                    response = client.document_text_detection(image=image)
                    if response.error.message: raise Exception(response.error.message)
                    full_text += response.full_text_annotation.text + "\n"
            return full_text
        elif uploaded_file.type in ["image/png", "image/jpeg", "image/jpg"]:
            image = vision.Image(content=file_bytes)
            response = client.document_text_detection(image=image)
            if response.error.message: raise Exception(response.error.message)
            return response.full_text_annotation.text
        return "Unsupported file type."
    except Exception as e:
        return f"Error calling Google Vision API: {str(e)}"

# --- DEFINITIVE PARSING LOGIC: HYBRID APPROACH ---
def parse_ocr_text(text: str):
    parsed_data = {"vendor": "N/A", "date": "N/A", "total_amount": 0.0, "gst_amount": 0.0, "pst_amount": 0.0, "hst_amount": 0.0, "line_items": []}
    lines = [line.strip() for line in text.split('\n') if line.strip()]

    # --- Keyword Definitions ---
    total_keywords = ["total"]
    subtotal_keywords = ["sous-total", "subtotal", "total partiel"]
    gst_keywords = ["tps", "gst", "federal tax"]
    pst_keywords = ["tvq", "qst", "tvp", "pst", "provincial tax"]
    hst_keywords = ["hst", "tvh"]
    
    # --- Line-by-Line Classification using Right-to-Left Parsing ---
    # This list will hold tuples of (line_index, description, price)
    potential_items = []
    
    line_pattern = re.compile(r'^(.*?)\s*([$]?\d+[.,]\d{2})[$]?\s*$')

    for i, line in enumerate(lines):
        match = line_pattern.match(line)
        if not match:
            continue

        description = match.group(1).strip()
        price = float(match.group(2).replace('$', '').replace(',', '.'))
        desc_lower = description.lower()

        # Use negative lookbehind to find "total" but not "subtotal"
        if re.search(r'(?<!sous-)(?<!sub)total', desc_lower):
            parsed_data['total_amount'] = max(parsed_data['total_amount'], price) # Take largest total
        elif any(kw in desc_lower for kw in gst_keywords):
            parsed_data['gst_amount'] = price
        elif any(kw in desc_lower for kw in pst_keywords):
            parsed_data['pst_amount'] = price
        elif any(kw in desc_lower for kw in hst_keywords):
            parsed_data['hst_amount'] = price
        elif any(kw in desc_lower for kw in subtotal_keywords):
            pass  # It's a subtotal, ignore for now
        else:
            # If no financial keywords match, it's a potential line item
            potential_items.append({'index': i, 'description': description, 'price': price})

    # --- "Look-Back" Logic to build multi-line item descriptions ---
    final_line_items = []
    for i, item in enumerate(potential_items):
        full_description = [item['description']]
        # Look at the lines immediately preceding the current item's line
        previous_line_index = item['index'] - 1
        
        # While the previous line exists and doesn't contain a price, it's part of the description
        while previous_line_index >= 0 and not line_pattern.match(lines[previous_line_index]):
            # Stop if we hit the description of a previously processed item
            if any(item_to_check['index'] == previous_line_index for item_to_check in potential_items):
                break
            
            description_part = lines[previous_line_index].strip()
            if len(description_part) > 1:
                full_description.insert(0, description_part)
            previous_line_index -= 1
        
        # Join the collected description lines
        final_description = " ".join(filter(None, full_description))
        
        # Filter out likely noise or accidental matches
        if len(final_description) > 2 and "merci" not in final_description.lower():
            final_line_items.append({'description': final_description, 'price': item['price']})

    parsed_data['line_items'] = final_line_items

    # --- Vendor and Date Post-Processing ---
    if lines:
        for line in lines[:5]:
            if len(line) > 3 and line.upper() == line and not any(kw in line.lower() for kw in ["invoice", "facture", "date", "caissier", "transaction"]):
                parsed_data["vendor"] = line
                break
    
    date_pattern = r'(\d{4}[-/\s]\d{1,2}[-/\s]\d{1,2})'
    if date_match := re.search(date_pattern, text):
        parsed_data["date"] = date_match.group(1).strip()

    return parsed_data

def extract_and_parse_file(uploaded_file):
    """Main pipeline function using Google Vision."""
    try:
        raw_text = extract_text_from_file(uploaded_file)
        if "Error" in raw_text:
             return raw_text, {"error": raw_text}
        
        parsed_data = parse_ocr_text(raw_text)
        return raw_text, parsed_data
        
    except Exception as e:
        error_message = f"A critical error occurred: {str(e)}"
        return error_message, {"error": error_message}
