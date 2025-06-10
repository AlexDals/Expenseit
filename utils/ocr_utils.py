import streamlit as st
from google.cloud import vision
import re
from itertools import combinations

# --- GOOGLE VISION API SETUP AND PREPROCESSING (No changes) ---
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

# --- DEFINITIVE PARSING LOGIC: RIGHT-TO-LEFT CLASSIFICATION ---
def parse_ocr_text(text: str):
    parsed_data = {"vendor": "N/A", "date": "N/A", "total_amount": 0.0, "gst_amount": 0.0, "pst_amount": 0.0, "hst_amount": 0.0, "line_items": []}
    lines = [line.strip() for line in text.split('\n') if line.strip()]

    # --- Keyword Definitions ---
    total_keywords = ["total"]
    subtotal_keywords = ["sous-total", "subtotal", "total partiel"]
    gst_keywords = ["tps", "gst", "federal"]
    pst_keywords = ["tvq", "qst", "tvp", "pst", "provincial"]
    hst_keywords = ["hst", "tvh"]
    
    # A robust regex to find lines ending in a price, capturing the description and price.
    line_pattern = re.compile(r'^(.*?)\s*([$]?\d+[.,]\d{2})$')

    for line in lines:
        match = line_pattern.match(line)
        if not match:
            continue

        description = match.group(1).strip()
        price = float(match.group(2).replace('$', '').replace(',', '.'))
        desc_lower = description.lower()

        # Classify the line based on keywords found in the description part
        # Using a negative lookbehind `(?<!...)` to find "total" but not "subtotal"
        if re.search(r'(?i)(?<!sous-)(?<!sub)total', desc_lower):
            parsed_data['total_amount'] = price
        elif any(kw in desc_lower for kw in gst_keywords):
            parsed_data['gst_amount'] = price
        elif any(kw in desc_lower for kw in pst_keywords):
            parsed_data['pst_amount'] = price
        elif any(kw in desc_lower for kw in hst_keywords):
            parsed_data['hst_amount'] = price
        elif any(kw in desc_lower for kw in subtotal_keywords):
            # It's a subtotal, we note it but don't add as a line item
            pass
        else:
            # If no financial keywords match, it's a line item.
            # Add checks to filter out irrelevant lines.
            if len(description) > 1 and not description.isdigit() and "merci" not in desc_lower:
                parsed_data["line_items"].append({'description': description, 'price': price})

    # --- Vendor and Date Post-Processing ---
    if lines:
        # Vendor is likely the first all-caps line that isn't a common word.
        for line in lines[:5]:
            if len(line) > 2 and line.upper() == line and not any(kw in line.lower() for kw in ["invoice", "facture", "date", "merci"]):
                parsed_data["vendor"] = line
                break
    
    # More flexible date matching
    date_patterns = [
        r'(\d{4}[-/\s]\d{1,2}[-/\s]\d{1,2})', # YYYY-MM-DD
        r'(\d{1,2}[-/\s]\d{1,2}[-/\s]\d{2,4})', # DD-MM-YYYY or MM-DD-YYYY
    ]
    for pattern in date_patterns:
        if date_match := re.search(pattern, text):
            parsed_data["date"] = date_match.group(1).strip()
            break

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
