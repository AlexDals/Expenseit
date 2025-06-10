import streamlit as st
from google.cloud import vision
import re

# --- GOOGLE VISION API SETUP (No changes) ---
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

# --- DEFINITIVE PARSING LOGIC: MODULAR & STATEFUL ---
def parse_ocr_text(text: str):
    parsed_data = {"vendor": "N/A", "date": "N/A", "total_amount": 0.0, "gst_amount": 0.0, "pst_amount": 0.0, "hst_amount": 0.0, "line_items": []}
    lines = [line.strip() for line in text.split('\n') if line.strip()]

    # --- Stage 1: Financial Summary Pass ---
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
                # Use max() to ensure we get the largest "Total" if multiple are found
                current_value = parsed_data.get(key, 0.0)
                parsed_data[key] = max(current_value, float(match.group(1).replace('$', '').replace(',', '.')))
                financial_line_indices.add(i)

    # --- Stage 2: Stateful Line Item Pass ---
    line_items = []
    current_description_lines = []
    # Regex to find a price anywhere on the line
    price_pattern = re.compile(r'(\d+[.,]\d{2})')
    # Regex for lines that are ONLY a price
    price_only_pattern = re.compile(r'^[$]?(\d+[.,]\d{2})[$]?$')
    
    for i, line in enumerate(lines):
        # Skip lines that were already identified as part of the financial summary
        if i in financial_line_indices:
            continue

        price_match = price_pattern.findall(line)
        
        # Scenario 1: Line contains only a price. It belongs to the description block above it.
        if price_only_pattern.match(line):
            if current_description_lines:
                price = float(line.replace('$', '').replace(',', '.'))
                full_description = " ".join(current_description_lines)
                line_items.append({"description": full_description, "price": price})
                current_description_lines = [] # Reset block
        # Scenario 2: Line contains text AND a price. It is a self-contained item.
        elif len(price_match) == 1:
            price = float(price_match[0].replace(',', '.'))
            # Extract description by removing the price and any surrounding whitespace/symbols
            description = re.sub(r'[$]?\d+[.,]\d{2}[$]?', '', line).strip()
            
            # If a description block was pending, it's a separate item without a price.
            # For now, we associate this price with this description.
            if description:
                line_items.append({"description": description, "price": price})
            current_description_lines = [] # Reset block
        # Scenario 3: Line contains no price. It is part of a description.
        else:
            current_description_lines.append(line)

    parsed_data["line_items"] = line_items
    
    # --- Stage 3: Vendor and Date Extraction ---
    if lines:
        for line in lines[:5]:
            if len(line) > 3 and line.upper() == line and not any(kw in line.lower() for kw in ["invoice", "facture", "date", "caissier", "transaction"]):
                parsed_data["vendor"] = line
                break
    
    date_pattern = r'(\d{4}[-/\s]\d{1,2}[-/\s]\d{1,2})|(\d{1,2}[-/\s]\d{1,2}[-/\s]\d{2,4})'
    if date_match := re.search(date_pattern, text):
        parsed_data["date"] = date_match.group(0).strip()

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
