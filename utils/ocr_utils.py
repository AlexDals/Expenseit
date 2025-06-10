import streamlit as st
from google.cloud import vision
import re

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

# --- DEFINITIVE PARSING LOGIC: PRICE-ANCHORED ---
def parse_ocr_text(text: str):
    """Parses OCR text using a robust price-anchored, block-partitioning system."""
    parsed_data = {"vendor": "N/A", "date": "N/A", "total_amount": 0.0, "gst_amount": 0.0, "pst_amount": 0.0, "hst_amount": 0.0, "line_items": []}
    lines = [line.strip() for line in text.split('\n') if line.strip()]

    # --- Stage 1: Basic Vendor and Date Extraction ---
    if lines:
        for line in lines[:5]:
            if len(line) > 3 and line.upper() == line and not any(kw in line.lower() for kw in ["invoice", "facture", "date", "caissier"]):
                parsed_data["vendor"] = line
                break
    
    date_pattern = r'(\d{4}[-/\s]\d{1,2}[-/\s]\d{1,2})|(\d{1,2}[-/\s]\d{1,2}[-/\s]\d{2,4})'
    if date_match := re.search(date_pattern, text):
        parsed_data["date"] = date_match.group(0).strip()

    # --- Stage 2: Financial Summary Pass ---
    # Extract financial data and log the line indices to exclude them from item parsing.
    financial_line_indices = set()
    financial_patterns = {
        'total_amount': re.compile(r'(?i)(?<!sous-)(?<!sub)total[:\s]*([$]?\s*\d+[.,]\d{2})'),
        'gst_amount': re.compile(r'(?i)(?:tps|gst)[\s:]*([$]?\s*\d+[.,]\d{2})'),
        'pst_amount': re.compile(r'(?i)(?:tvq|qst|pst)[\s:]*([$]?\s*\d+[.,]\d{2})'),
        'subtotal': re.compile(r'(?i)(?:sous-total|subtotal|ecofrais)[\s:]*([$]?\s*\d+[.,]\d{2})')
    }
    for i, line in enumerate(lines):
        for key, pattern in financial_patterns.items():
            if match := pattern.search(line):
                parsed_data[key] = max(parsed_data.get(key, 0.0), float(match.group(1).replace('$', '').replace(',', '.')))
                financial_line_indices.add(i)

    # --- Stage 3: Price-Anchored Block Parsing for Line Items ---
    final_line_items = []
    
    # First, find all potential item prices and their line numbers
    price_pattern = re.compile(r'(\d+[.,]\d{2})$')
    item_price_anchors = []
    
    start_index = 0
    # Find start of item section (heuristic: after vendor/address info)
    for i, line in enumerate(lines):
        if len(line) > 30 and ("description" in line.lower() or "quantit" in line.lower()):
            start_index = i + 1
            break
            
    for i in range(start_index, len(lines)):
        if i in financial_line_indices:
            continue
        if match := price_pattern.search(lines[i]):
            price = float(match.group(1).replace(',', '.'))
            item_price_anchors.append({'index': i, 'price': price})

    # Now, build description blocks based on the space between price anchors
    last_price_index = start_index -1
    for anchor in item_price_anchors:
        current_price_index = anchor['index']
        price = anchor['price']
        
        # The description is all the lines between the last price and this one
        description_lines = []
        for i in range(last_price_index + 1, current_price_index + 1):
             # Clean the line by removing the price from it
            cleaned_line = re.sub(r'\s*[$]?'+re.escape(f"{price:.2f}")+r'[$]?', '', lines[i]).strip()
            if cleaned_line:
                description_lines.append(cleaned_line)
        
        if description_lines:
            full_description = " ".join(description_lines)
            final_line_items.append({"description": full_description, "price": price})
        
        last_price_index = current_price_index

    parsed_data['line_items'] = final_line_items
    
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
