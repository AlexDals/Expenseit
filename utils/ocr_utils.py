import pytesseract
from PIL import Image
import io
import re
import fitz  # PyMuPDF
import cv2  # OpenCV
import numpy as np
from google.cloud import vision
import streamlit as st

# --- GOOGLE VISION API AND IMAGE PREPROCESSING ---
@st.cache_resource
def get_vision_client():
    """Initializes and returns a Google Vision API client."""
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
        image = vision.Image(content=file_bytes)
        response = client.document_text_detection(image=image)
        if response.error.message:
            raise Exception(f"{response.error.message}")
        return response.full_text_annotation.text
    except Exception as e:
        return f"Error calling Google Vision API: {str(e)}"


# --- DEFINITIVE PARSING LOGIC: MULTI-STAGE ---
def parse_ocr_text(text: str):
    parsed_data = {"vendor": "N/A", "date": "N/A", "total_amount": 0.0, "gst_amount": 0.0, "pst_amount": 0.0, "hst_amount": 0.0, "line_items": []}
    lines = [line.strip() for line in text.split('\n') if line.strip()]

    # --- Stage 1: Basic Vendor and Date Extraction ---
    if lines:
        for line in lines[:5]:
            if len(line) > 3 and line.upper() == line and not any(kw in line.lower() for kw in ["invoice", "facture", "date", "caissier"]):
                parsed_data["vendor"] = line
                break
    
    date_pattern = r'(\d{2,4}[-/\s]\d{1,2}[-/\s]\d{1,2})'
    if date_match := re.search(date_pattern, text):
        parsed_data["date"] = date_match.group(1).strip()

    # --- Stage 2: Pre-scan and extract all financial summary lines ---
    financial_lines = {}
    item_lines = []
    
    # Keywords must be specific to avoid misclassification
    total_keywords = ["total"]
    subtotal_keywords = ["sous-total", "subtotal"]
    gst_keywords = ["tps", "gst"]
    pst_keywords = ["tvq", "qst"]
    hst_keywords = ["hst", "tvh"]
    all_financial_keywords = total_keywords + subtotal_keywords + gst_keywords + pst_keywords + hst_keywords
    
    # Regex to find a keyword and its value on the same line
    financial_pattern = re.compile(r'^(.*?)\s*([$]?\d+[.,]\d{2})$')

    for i, line in enumerate(lines):
        line_lower = line.lower()
        
        is_financial = False
        for kw_list, kw_name in [(total_keywords, 'total'), (subtotal_keywords, 'subtotal'), (gst_keywords, 'gst'), (pst_keywords, 'pst'), (hst_keywords, 'hst')]:
            if any(kw in line_lower for kw in kw_list):
                if match := financial_pattern.match(line):
                    price = float(match.group(2).replace('$', '').replace(',', '.'))
                    # Use a negative lookbehind for total to avoid subtotal
                    if kw_name == 'total' and re.search(r'(?i)(?<!sous-)(?<!sub)total', line_lower):
                        parsed_data['total_amount'] = price
                    elif kw_name == 'gst':
                        parsed_data['gst_amount'] = price
                    elif kw_name == 'pst':
                        parsed_data['pst_amount'] = price
                    elif kw_name == 'hst':
                        parsed_data['hst_amount'] = price
                is_financial = True
                break
        
        if not is_financial:
            item_lines.append(line)

    # --- Stage 3: Stateful parsing for line items from the remaining lines ---
    line_items = []
    current_description_lines = []
    price_only_pattern = re.compile(r'^[$]?(\d+[.,]\d{2})[$]?$')
    
    for line in item_lines:
        # Check if the line is just a price
        if price_match := price_only_pattern.match(line):
            price = float(price_match.group(1).replace(',', '.'))
            if current_description_lines:
                full_description = " ".join(current_description_lines)
                line_items.append({"description": full_description, "price": price})
                current_description_lines = [] # Reset
        # Check if the line has description and price
        elif item_match := financial_pattern.match(line):
            description, price_str = item_match.groups()
            price = float(price_str.replace('$', '').replace(',', '.'))
            
            # If there was a description block, this price belongs to it
            if current_description_lines:
                 current_description_lines.append(description)
                 full_description = " ".join(current_description_lines)
                 line_items.append({"description": full_description, "price": price})
                 current_description_lines = [] # Reset
            else: # It's a single line item
                 line_items.append({"description": description, "price": price})
        else:
            # It's a description line
            current_description_lines.append(line)
            
    parsed_data["line_items"] = line_items
    
    # --- Final fallback for total if keyword search failed ---
    if parsed_data["total_amount"] == 0.0:
        all_amounts = [float(m.replace(',', '.')) for m in re.findall(r'(\d+[.,]\d{2})', text)]
        if all_amounts:
            parsed_data["total_amount"] = max(all_amounts)

    return parsed_data

def extract_and_parse_file(uploaded_file):
    """Main pipeline function."""
    try:
        raw_text = extract_text_from_file(uploaded_file)
        if "Error" in raw_text or "Unsupported" in raw_text:
             return raw_text, {"error": raw_text}
        parsed_data = parse_ocr_text(raw_text)
        return raw_text, parsed_data
    except Exception as e:
        error_message = f"A critical error occurred: {str(e)}"
        return error_message, {"error": error_message}
