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

# --- DEFINITIVE PARSING LOGIC: ITEM SEPARATOR APPROACH ---
def parse_ocr_text(text: str):
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
    # Extract all financial data first and log the lines to exclude them from item parsing.
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
                parsed_data[key] = max(parsed_data.get(key, 0.0), float(match.group(1).replace('$', '').replace(',', '.')))
                financial_line_indices.add(i)

    # --- Stage 3: Block-Based Line Item Extraction ---
    item_blocks = []
    current_block = []
    
    # Heuristic: A line starting with a number and a capitalized word is an item separator.
    item_separator_pattern = re.compile(r'^\d\s+[A-Z0-9]+')
    
    # Isolate only the lines that could possibly be part of an item
    item_lines_with_indices = [(i, lines[i]) for i in range(len(lines)) if i not in financial_line_indices]

    for i, line in item_lines_with_indices:
        # If we find a separator, it's the start of a new item block.
        # The previous block is now complete.
        if item_separator_pattern.match(line):
            if current_block:
                item_blocks.append(current_block)
            current_block = [line] # Start a new block with the separator line
        else:
            current_block.append(line)
    
    # Append the last block after the loop finishes
    if current_block:
        item_blocks.append(current_block)

    # Now, parse each block to find one description and one price
    final_line_items = []
    price_pattern = re.compile(r'(\d+[.,]\d{2})$')

    for block in item_blocks:
        price = 0.0
        description_parts = []
        for line in block:
            if match := price_pattern.search(line):
                price = max(price, float(match.group(1).replace(',', '.')))
                # Add the text before the price as part of the description
                desc_part = line[:match.start()].strip()
                if desc_part:
                    description_parts.append(desc_part)
            else:
                description_parts.append(line)
        
        if price > 0:
            # Join all parts and clean up
            full_description = " ".join(filter(None, description_parts)).strip()
            if full_description:
                final_line_items.append({"description": full_description, "price": price})

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
