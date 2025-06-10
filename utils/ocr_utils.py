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

# --- DEFINITIVE PARSING LOGIC: "RIGHT-TO-LEFT" WITH MULTI-LINE LOOK-BACK ---
def parse_ocr_text(text: str):
    parsed_data = {"vendor": "N/A", "date": "N/A", "total_amount": 0.0, "gst_amount": 0.0, "pst_amount": 0.0, "hst_amount": 0.0, "line_items": []}
    lines = [line.strip() for line in text.split('\n') if line.strip()]

    # --- Keyword Definitions ---
    total_keywords = ["total"]
    subtotal_keywords = ["sous-total", "subtotal", "total partiel"]
    gst_keywords = ["tps", "gst"]
    pst_keywords = ["tvq", "qst", "pst"]
    hst_keywords = ["hst", "tvh"]
    
    # --- Stage 1: Classify all lines with a price ---
    classified_items = []
    line_pattern = re.compile(r'^(.*?)\s*([$]?\d+[.,]\d{2})[$]?\s*$')

    for i, line in enumerate(lines):
        match = line_pattern.match(line)
        if not match:
            continue

        description = match.group(1).strip()
        price = float(match.group(2).replace('$', '').replace(',', '.'))
        desc_lower = description.lower()
        
        item_type = 'item' 
        
        # Use a negative lookbehind to find "total" but not "subtotal"
        if re.search(r'(?i)(?<!sous-)(?<!sub)total', desc_lower):
            item_type = 'total'
        elif any(kw in desc_lower for kw in gst_keywords):
            item_type = 'gst'
        elif any(kw in desc_lower for kw in pst_keywords):
            item_type = 'pst'
        elif any(kw in desc_lower for kw in hst_keywords):
            item_type = 'hst'
        elif any(kw in desc_lower for kw in subtotal_keywords):
            item_type = 'subtotal'
        
        classified_items.append({'index': i, 'description': description, 'price': price, 'type': item_type})

    # --- Stage 2: Assign Financials and intelligently process Line Items ---
    final_line_items = []
    processed_indices = set()

    for item in classified_items:
        if item['type'] == 'total':
            parsed_data['total_amount'] = item['price']
            processed_indices.add(item['index'])
        elif item['type'] == 'gst':
            parsed_data['gst_amount'] = item['price']
            processed_indices.add(item['index'])
        elif item['type'] == 'pst':
            parsed_data['pst_amount'] = item['price']
            processed_indices.add(item['index'])
        elif item['type'] == 'hst':
            parsed_data['hst_amount'] = item['price']
            processed_indices.add(item['index'])
        elif item['type'] == 'subtotal':
            processed_indices.add(item['index'])
    
    # "Look-Back" logic for items
    for item in classified_items:
        if item['type'] == 'item':
            # This item has already been fully described on one line
            if item['description']:
                final_line_items.append({'description': item['description'], 'price': item['price']})
            else:
                # If description is empty, look backwards for multi-line description
                full_description_lines = []
                lookup_index = item['index'] - 1
                while lookup_index >= 0:
                    # Stop if the previous line was a financial line or part of another item
                    if lookup_index in processed_indices or any(i['index'] == lookup_index for i in classified_items):
                        break
                    
                    line_text = lines[lookup_index]
                    full_description_lines.insert(0, line_text)
                    lookup_index -= 1

                if full_description_lines:
                    final_line_items.append({'description': " ".join(full_description_lines), 'price': item['price']})
    
    parsed_data['line_items'] = final_line_items

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
