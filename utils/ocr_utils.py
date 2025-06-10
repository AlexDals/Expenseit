import pytesseract
from PIL import Image
import io
import re
import fitz  # PyMuPDF
import cv2  # OpenCV
import numpy as np
from google.cloud import vision
import streamlit as st

# --- GOOGLE VISION API SETUP ---
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
    """Extracts text from a file using Google Cloud Vision AI."""
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

# --- DEFINITIVE PARSING LOGIC: LINE-BY-LINE CLASSIFICATION ---
def parse_ocr_text(text: str):
    """Parses OCR text using targeted, line-by-line regular expressions."""
    parsed_data = {"vendor": "N/A", "date": "N/A", "total_amount": 0.0, "gst_amount": 0.0, "pst_amount": 0.0, "hst_amount": 0.0, "line_items": []}
    lines = [line.strip() for line in text.split('\n') if line.strip()]

    # --- Regex Definitions ---
    # Negative lookbehind `(?i)(?<!...)` ensures we match "Total" but not "Subtotal" / "Sous-total"
    total_pattern = re.compile(r'(?i)(?<!sous-)(?<!sub)total[:\s]*([$]?\s*\d+[.,]\d{2})')
    subtotal_pattern = re.compile(r'(?i)(?:sous-total|subtotal)[:\s]*([$]?\s*\d+[.,]\d{2})')
    tps_pattern = re.compile(r'(?i)(?:tps|gst)[\s:]*([$]?\s*\d+[.,]\d{2})')
    tvq_pattern = re.compile(r'(?i)(?:tvq|qst|pst)[\s:]*([$]?\s*\d+[.,]\d{2})')
    hst_pattern = re.compile(r'(?i)(?:hst|tvh)[\s:]*([$]?\s*\d+[.,]\d{2})')
    
    # A line item is assumed to be text that ends with a price
    line_item_pattern = re.compile(r'^(.*?)\s+([$]?\d+[.,]\d{2})$')

    # --- Data Extraction Pass ---
    for line in lines:
        # These keywords identify lines that are NOT line items
        financial_keywords = ["total", "sous-total", "subtotal", "tps", "gst", "tvq", "qst", "hst", "tvh", "ecofrais", "tip", "pourboire"]
        
        # We check in order of importance
        if match := total_pattern.search(line):
            parsed_data['total_amount'] = float(match.group(1).replace('$', '').replace(',', '.'))
        elif match := tps_pattern.search(line):
            parsed_data['gst_amount'] = float(match.group(1).replace('$', '').replace(',', '.'))
        elif match := tvq_pattern.search(line):
            parsed_data['pst_amount'] = float(match.group(1).replace('$', '.'))
        elif match := hst_pattern.search(line):
            parsed_data['hst_amount'] = float(match.group(1).replace('$', '').replace(',', '.'))
        elif match := line_item_pattern.match(line):
            # If the line is not a summary line, treat it as a line item
            if not any(keyword in line.lower() for keyword in financial_keywords):
                description = match.group(1).strip()
                price = float(match.group(2).replace('$', '').replace(',', '.'))
                # Additional check to filter out irrelevant lines
                if len(description) > 2 and "merci" not in description.lower() and "approved" not in description.lower():
                    parsed_data["line_items"].append({"description": description, "price": price})

    # --- Vendor and Date Extraction ---
    if lines:
        # Heuristic: First significant capitalized line is often the vendor
        for line in lines[:5]:
            if len(line) > 3 and line.upper() == line and not any(kw in line.lower() for kw in ["invoice", "facture", "date", "caissier", "transaction"]):
                parsed_data["vendor"] = line
                break
    
    date_pattern = r'(\d{4}[-/\s]\d{1,2}[-/\s]\d{1,2})' # YYYY-MM-DD is most reliable
    date_match = re.search(date_pattern, text)
    if date_match:
        parsed_data["date"] = date_match.group(1).strip()
    
    return parsed_data

# --- Main Entry Point Function ---
def extract_and_parse_file(uploaded_file):
    """Main pipeline function using Google Vision."""
    try:
        raw_text = extract_text_from_file(uploaded_file)
        if "Error" in raw_text or "Unsupported" in raw_text:
             return raw_text, {"error": raw_text}
        parsed_data = parse_ocr_text(raw_text)
        return raw_text, parsed_data
    except Exception as e:
        error_message = f"A critical error occurred: {str(e)}"
        return error_message, {"error": error_message}
