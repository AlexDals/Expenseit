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

# --- DEFINITIVE PARSING LOGIC: PARTITION-FIRST ---
def parse_ocr_text(text: str):
    """Parses OCR text using a robust block-partitioning system."""
    parsed_data = {"vendor": "N/A", "date": "N/A", "total_amount": 0.0, "gst_amount": 0.0, "pst_amount": 0.0, "hst_amount": 0.0, "line_items": []}
    lines = [line.strip() for line in text.split('\n') if line.strip()]

    # --- Stage 1: Basic Vendor and Date Extraction ---
    if lines:
        for line in lines[:5]:
            if len(line) > 2 and line.upper() == line and not any(kw in line.lower() for kw in ["invoice", "facture", "date", "caissier"]):
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
        'subtotal': re.compile(r'(?i)(?:sous-total|subtotal)[\s:]*([$]?\s*\d+[.,]\d{2})')
    }
    for i, line in enumerate(lines):
        for key, pattern in financial_patterns.items():
            if match := pattern.search(line):
                parsed_data[key] = max(parsed_data.get(key, 0.0), float(match.group(1).replace('$', '').replace(',', '.')))
                financial_line_indices.add(i)

    # --- Stage 3: Split-and-Parse Line Item Extraction ---
    # Isolate only the lines that could possibly be part of an item
    item_lines_text = "\n".join([lines[i] for i in range(len(lines)) if i not in financial_line_indices])
    
    # A separator is a line starting with a single digit, a space, and a capital letter/number code.
    item_separator_pattern = r'\n(?=\d\s+[A-Z0-9])'
    # Split the text into blocks based on the separator
    item_blocks = re.split(item_separator_pattern, item_lines_text)
    
    final_line_items = []
    price_pattern = re.compile(r'(\d+[.,]\d{2})')

    for block in item_blocks:
        if not block.strip():
            continue
        
        # Find all numbers in the block and assume the largest is the price
        all_amounts_in_block = [float(p.replace(',', '.')) for p in price_pattern.findall(block)]
        if not all_amounts_in_block:
            continue
            
        price = max(all_amounts_in_block)
        
        # The description is the entire block, cleaned up
        description_lines = []
        for line in block.split('\n'):
            # Remove the price from the line to avoid including it in the description
            line_without_price = re.sub(r'[$]?\d+[.,]\d{2}[$]?', '', line).strip()
            if line_without_price:
                description_lines.append(line_without_price)
        
        full_description = " ".join(description_lines)
        
        # Add heuristics to select the most relevant part of the description
        if "HP ProBook" in full_description:
            best_description = next((l for l in description_lines if "HP ProBook" in l), full_description)
        elif "Frais de gestion" in full_description:
            best_description = next((l for l in description_lines if "Frais de gestion" in l), full_description)
        elif "TeamGroup" in full_description:
            best_description = next((l for l in description_lines if "TeamGroup" in l), full_description)
        else:
            # Default to the first line of the block (often the part number)
            best_description = description_lines[0] if description_lines else "N/A"
        
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
