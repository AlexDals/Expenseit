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

# --- DEFINITIVE PARSING LOGIC ---
def parse_ocr_text(text: str):
    """Parses OCR text using a robust two-pass, block-aware system."""
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
    # Find and extract financial data first, and keep track of which lines they were on.
    financial_line_indices = set()
    financial_patterns = {
        'total_amount': re.compile(r'(?i)(?<!sous-)(?<!sub)total[:\s]*([$]?\s*\d+[.,]\d{2})'),
        'gst_amount': re.compile(r'(?i)(?:tps|gst)[\s:]*([$]?\s*\d+[.,]\d{2})'),
        'pst_amount': re.compile(r'(?i)(?:tvq|qst|pst)[\s:]*([$]?\s*\d+[.,]\d{2})'),
        'subtotal': re.compile(r'(?i)(?:sous-total|subtotal)[\s:]*([$]?\s*\d+[.,]\d{2})')
    }
    for i, line in enumerate(lines):
        for key, pattern in financial_patterns.items():
            if match := pattern.search(line):
                # Use a temporary dict to avoid overwriting if total is found twice
                parsed_data[key] = max(parsed_data.get(key, 0.0), float(match.group(1).replace('$', '').replace(',', '.')))
                financial_line_indices.add(i)
    
    # --- Stage 3: Block-Aware Line Item Extraction ---
    line_items = []
    current_desc_block = []
    price_pattern = re.compile(r'([$]?\d+[.,]\d{2})$') # Price at the end of the line

    # Process only the lines that were not identified as financial summary lines
    for i, line in enumerate(lines):
        if i in financial_line_indices:
            continue

        match = price_pattern.search(line)

        # If a price is found, it marks the end of an item block
        if match:
            price = float(match.group(1).replace('$', '').replace(',', '.'))
            description_part = line[:match.start()].strip()
            
            # Add the text on the current line (if any) to the block
            if description_part:
                current_desc_block.append(description_part)

            # Finalize the item if we have a description
            if current_desc_block:
                full_description = " ".join(current_desc_block)
                line_items.append({"description": full_description, "price": price})
            
            # Reset for the next item
            current_desc_block = []
        else:
            # If no price, this line is part of a description block
            current_desc_block.append(line)
            
    parsed_data["line_items"] = line_items
    
    # Final fallback for total if keyword search failed
    if parsed_data.get("total_amount", 0.0) == 0.0:
        all_amounts = [float(m.replace(',', '.')) for m in re.findall(r'(\d+[.,]\d{2})', text)]
        if all_amounts:
            parsed_data["total_amount"] = max(all_amounts)

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
