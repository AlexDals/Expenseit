import streamlit as st
from google.cloud import vision
import re

# --- GOOGLE VISION API SETUP AND TEXT EXTRACTION ---
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

# --- DEFINITIVE PARSING LOGIC: PRICE-ANCHORED BLOCKS ---
def parse_ocr_text(text: str):
    """Parses OCR text using a robust block-partitioning system anchored by prices."""
    parsed_data = {"vendor": "N/A", "date": "N/A", "total_amount": 0.0, "gst_amount": 0.0, "pst_amount": 0.0, "hst_amount": 0.0, "line_items": []}
    lines = [line.strip() for line in text.split('\n') if line.strip()]

    # --- Stage 1: Basic Vendor and Date Extraction ---
    if lines:
        # Vendor is likely the first all-caps line
        for line in lines[:5]:
            if len(line) > 3 and line.upper() == line and not any(kw in line.lower() for kw in ["invoice", "facture", "date", "caissier"]):
                parsed_data["vendor"] = line
                break
    
    date_pattern = r'(\d{4}[-/\s]\d{1,2}[-/\s]\d{1,2})|(\d{1,2}[-/\s]\d{1,2}[-/\s]\d{2,4})'
    if date_match := re.search(date_pattern, text):
        parsed_data["date"] = date_match.group(0).strip()

    # --- Stage 2: Financial Summary Pass ---
    # This pass finds the totals and taxes using direct keyword matching.
    financial_patterns = {
        'total_amount': re.compile(r'(?i)(?<!sous-)(?<!sub)total[:\s]*([$]?\s*\d+[.,]\d{2})'),
        'gst_amount': re.compile(r'(?i)(?:tps|gst)[\s:]*([$]?\s*\d+[.,]\d{2})'),
        'pst_amount': re.compile(r'(?i)(?:tvq|qst|pst)[\s:]*([$]?\s*\d+[.,]\d{2})'),
        'subtotal_val': re.compile(r'(?i)(?:sous-total|subtotal)[\s:]*([$]?\s*\d+[.,]\d{2})')
    }
    financial_values = {}
    for key, pattern in financial_patterns.items():
        if match := pattern.search(text):
            financial_values[key] = float(match.group(1).replace('$', '').replace(',', '.'))
    parsed_data.update(financial_values)

    # --- Stage 3: Price-Anchored Block Parsing for Line Items ---
    line_items = []
    
    # Find all potential prices and their line numbers
    price_pattern = re.compile(r'(\d+[.,]\d{2})$')
    prices_with_indices = []
    for i, line in enumerate(lines):
        if match := price_pattern.search(line):
            price = float(match.group(1).replace(',', '.'))
            # Exclude prices that we know are part of the financial summary
            if not any(abs(price - val) < 0.01 for val in financial_values.values()):
                prices_with_indices.append({'index': i, 'price': price})

    # Partition the document into blocks based on the location of prices
    start_index = 0
    for price_info in prices_with_indices:
        end_index = price_info['index']
        price = price_info['price']
        
        # The block is all lines between the last item and this one
        block_lines = [lines[i] for i in range(start_index, end_index + 1)]
        
        # Heuristic to find the best description within the block
        # Prefers longer, non-all-caps lines.
        best_description = ""
        candidate_lines = []
        for line in block_lines:
            # Clean the line by removing the price from it
            cleaned_line = re.sub(r'[$]?\d+[.,]\d{2}[$]?', '', line).strip()
            if len(cleaned_line) > 2:
                candidate_lines.append(cleaned_line)
        
        if candidate_lines:
            # Find the longest line in the block that is not all caps
            non_caps_candidates = [l for l in candidate_lines if not (l.isupper() and len(l.split()) < 4)]
            if non_caps_candidates:
                best_description = max(non_caps_candidates, key=len)
            else: # Fallback to the first line if all are caps/codes
                best_description = candidate_lines[0]
                
        if best_description:
            line_items.append({"description": best_description, "price": price})
            
        # The start for the next block is after the current price's line
        start_index = end_index + 1
            
    parsed_data['line_items'] = line_items
    
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
