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

# --- DEFINITIVE PARSING LOGIC: PARTITION-FIRST ---
def parse_ocr_text(text: str):
    """Parses OCR text using a robust block-partitioning system."""
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
                # Use max() to ensure we get the largest "Total" if multiple are found
                parsed_data[key] = max(parsed_data.get(key, 0.0), float(match.group(1).replace('$', '').replace(',', '.')))
                financial_line_indices.add(i)

    # --- Stage 3: Partition and Parse Line Items ---
    # Isolate only the lines that could possibly be part of an item
    item_lines_text = "\n".join([lines[i] for i in range(len(lines)) if i not in financial_line_indices])
    
    # A separator is a line starting with a single digit, a space, and a capital letter/number code.
    # We use a lookahead `(?=...)` in re.split to keep the separator as the start of the next block.
    item_separator_pattern = r'(?=\n\d\s+[A-Z0-9])'
    item_blocks = re.split(item_separator_pattern, item_lines_text)
    
    final_line_items = []
    price_pattern = re.compile(r'(\d+[.,]\d{2})')

    for block in item_blocks:
        block = block.strip()
        if not block:
            continue
        
        all_amounts_in_block = [float(p.replace(',', '.')) for p in price_pattern.findall(block)]
        if not all_amounts_in_block:
            continue
            
        price = max(all_amounts_in_block)
        
        # Heuristic: The best description is the longest line in the block that is not all-caps
        description_lines = [line.strip() for line in block.split('\n') if line.strip()]
        
        best_description = ""
        # Prefer longer lines that are not all-caps (which are often product codes)
        human_readable_lines = [l for l in description_lines if not (l.isupper() and len(l.split()) < 4) and not price_pattern.search(l)]
        
        if human_readable_lines:
            best_description = max(human_readable_lines, key=len)
        else: # Fallback to the first line of the block if all are codes/caps
            # Clean the first line from any price
            first_line_cleaned = re.sub(r'\s*[$]?\d+[.,]\d{2}[$]?\s*$', '', block_lines[0]).strip()
            best_description = first_line_cleaned if first_line_cleaned else "N/A"
            
        final_line_items.append({"description": best_description.strip(), "price": price})

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
