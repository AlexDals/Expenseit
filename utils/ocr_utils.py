import pytesseract
from PIL import Image
import io
import re
import fitz  # PyMuPDF
import cv2  # OpenCV
import numpy as np
from google.cloud import vision
import streamlit as st
import pandas as pd

# --- GOOGLE VISION API SETUP AND PREPROCESSING ---
@st.cache_resource
def get_vision_client():
    """Initializes a Google Vision API client."""
    try:
        credentials_dict = dict(st.secrets.google_credentials)
        client = vision.ImageAnnotatorClient.from_service_account_info(credentials_dict)
        return client
    except Exception as e:
        st.error(f"Could not initialize Google Vision API client: {e}")
        st.stop()

def get_structured_data_from_file(uploaded_file):
    """
    Performs OCR using Google Vision and returns a structured pandas DataFrame
    with text and coordinate information for each word.
    """
    client = get_vision_client()
    file_bytes = uploaded_file.getvalue()
    full_text_annotation = None
    
    try:
        # For PDF, process page by page and combine results
        if uploaded_file.type == "application/pdf":
            input_requests = []
            with fitz.open(stream=file_bytes, filetype="pdf") as doc:
                for page in doc:
                    pix = page.get_pixmap(dpi=300)
                    img_bytes = pix.tobytes("png")
                    image = vision.Image(content=img_bytes)
                    feature = vision.Feature(type_=vision.Feature.Type.DOCUMENT_TEXT_DETECTION)
                    input_requests.append({"image": image, "features": [feature]})
            
            response = client.batch_annotate_images(requests=input_requests)
            # Combine text from all pages
            all_pages_text = ""
            for image_response in response.responses:
                if image_response.error.message:
                    raise Exception(image_response.error.message)
                all_pages_text += image_response.full_text_annotation.text
            return all_pages_text

        # For images, process directly
        elif uploaded_file.type in ["image/png", "image/jpeg", "image/jpg"]:
            image = vision.Image(content=file_bytes)
            response = client.document_text_detection(image=image)
            if response.error.message:
                raise Exception(response.error.message)
            return response.full_text_annotation.text
        
        else:
            return "Unsupported file type."

    except Exception as e:
        return f"Error calling Google Vision API: {str(e)}"

# --- DEFINITIVE PARSING LOGIC: GEOMETRIC (Right-to-Left) ---
def parse_ocr_text(text: str):
    """Parses OCR text using a robust line-by-line classification method."""
    parsed_data = {"vendor": "N/A", "date": "N/A", "total_amount": 0.0, "gst_amount": 0.0, "pst_amount": 0.0, "hst_amount": 0.0, "line_items": []}
    lines = [line.strip() for line in text.split('\n') if line.strip()]

    # --- Keyword Definitions ---
    total_keywords = ["total"]
    subtotal_keywords = ["sous-total", "subtotal"]
    gst_keywords = ["tps", "gst"]
    pst_keywords = ["tvq", "qst", "pst"]
    hst_keywords = ["hst", "tvh"]
    financial_keywords = total_keywords + subtotal_keywords + gst_keywords + pst_keywords + hst_keywords
    
    # --- Line-by-Line Classification ---
    line_pattern = re.compile(r'^(.*?)\s*([$]?\d+[.,]\d{2})[$]?\s*$')
    
    # First pass to get financial data
    for line in lines:
        match = line_pattern.match(line)
        if not match: continue
        
        description = match.group(1).strip()
        price = float(match.group(2).replace('$', '').replace(',', '.'))
        desc_lower = description.lower()

        if re.search(r'(?<!sous-)(?<!sub)total', desc_lower):
            parsed_data['total_amount'] = price
        elif any(kw in desc_lower for kw in gst_keywords):
            parsed_data['gst_amount'] = price
        elif any(kw in desc_lower for kw in pst_keywords):
            parsed_data['pst_amount'] = price
        elif any(kw in desc_lower for kw in hst_keywords):
            parsed_data['hst_amount'] = price
    
    # Second pass for line items
    temp_line_items = []
    for i, line in enumerate(lines):
        match = line_pattern.match(line)
        if not match: continue
        
        description = match.group(1).strip()
        price = float(match.group(2).replace('$', '').replace(',', '.'))
        desc_lower = description.lower()
        
        # Check if it's a financial line. If so, skip it.
        is_financial = any(kw in desc_lower for kw in financial_keywords)
        if not is_financial and len(description) > 1 and "merci" not in desc_lower:
            temp_line_items.append({'original_index': i, 'description': description, 'price': price})

    # "Look-back" logic to combine multi-line descriptions
    final_line_items = []
    processed_indices = set()
    for item in temp_line_items:
        if item['original_index'] in processed_indices:
            continue
            
        full_description = [item['description']]
        price = item['price']
        
        # Check if the description is empty, if so, look up
        if not item['description']:
            lookup_index = item['original_index'] - 1
            desc_buffer = []
            while lookup_index >= 0:
                prev_line = lines[lookup_index]
                # If the previous line has a price, it's another item, so stop.
                if line_pattern.match(prev_line):
                    break
                # If the previous line is just text, prepend it.
                desc_buffer.insert(0, prev_line)
                processed_indices.add(lookup_index)
                lookup_index -= 1
            full_description = desc_buffer
        
        final_line_items.append({'description': ' '.join(full_description), 'price': price})
        processed_indices.add(item['original_index'])

    parsed_data['line_items'] = final_line_items

    # --- Vendor and Date Extraction ---
    if lines:
        for line in lines[:5]:
            if len(line) > 3 and line.upper() == line and not any(kw in line.lower() for kw in ["invoice", "facture", "date", "caissier"]):
                parsed_data["vendor"] = line
                break
    
    date_pattern = r'(\d{4}[-/\s]\d{1,2}[-/\s]\d{1,2})'
    if date_match := re.search(date_pattern, text):
        parsed_data["date"] = date_match.group(1).strip()
    
    return parsed_data

def extract_and_parse_file(uploaded_file):
    """Main pipeline function using Google Vision."""
    try:
        raw_text = get_structured_data_from_file(uploaded_file)
        if "Error" in raw_text or "Unsupported" in raw_text:
             return raw_text, {"error": raw_text}
        
        parsed_data = parse_ocr_text(raw_text)
        return raw_text, parsed_data
    except Exception as e:
        error_message = f"A critical error occurred: {str(e)}"
        return error_message, {"error": error_message}
