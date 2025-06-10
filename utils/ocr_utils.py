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

# --- DEFINITIVE PARSING LOGIC: BLOCK-AWARE ---
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
    financial_line_indices = set()
    financial_data = {}
    
    financial_patterns = {
        'total_amount': re.compile(r'(?i)(?<!sous-)(?<!sub)total[:\s]*([$]?\s*\d+[.,]\d{2})'),
        'gst_amount': re.compile(r'(?i)(?:tps|gst)[\s:]*([$]?\s*\d+[.,]\d{2})'),
        'pst_amount': re.compile(r'(?i)(?:tvq|qst|pst)[\s:]*([$]?\s*\d+[.,]\d{2})'),
        'subtotal': re.compile(r'(?i)(?:sous-total|subtotal)[\s:]*([$]?\s*\d+[.,]\d{2})')
    }

    for i, line in enumerate(lines):
        for key, pattern in financial_patterns.items():
            if match := pattern.search(line):
                financial_data[key] = float(match.group(1).replace('$', '').replace(',', '.'))
                financial_line_indices.add(i)
                break # Move to next line once a match is found
    
    parsed_data.update(financial_data)

    # --- Stage 3: Block-Based Line Item Extraction ---
    line_items = []
    item_lines = [lines[i] for i in range(len(lines)) if i not in financial_line_indices]
    
    current_block = []
    for line in item_lines:
        # A price on a line typically signifies the end of an item block
        price_match = re.search(r'(\d+[.,]\d{2})$', line)
        
        current_block.append(line)
        if price_match:
            price = float(price_match.group(1).replace(',', '.'))
            
            # Find the most plausible description within the block
            description = ""
            # Heuristic: The best description is often a capitalized line that is not a part number
            for block_line in current_block:
                if len(block_line) > len(description) and not block_line.isupper() and len(re.findall(r'\d', block_line)) < 5:
                    description = block_line
            
            # Fallback if no good description is found
            if not description and len(current_block) > 1:
                # Often the part number is on the first line of the block
                # and the price on the last, so we take the first line.
                description = current_block[0]
            elif not description:
                 # Handle case where desc and price are on the same line
                 desc_part = re.match(r'^(.*?)\s+[\d.,]+\d{2}$', " ".join(current_block))
                 if desc_part:
                     description = desc_part.group(1)

            # Cleanup and add
            if description:
                # Remove the price from the description if it's there
                description = description.replace(price_match.group(0), "").strip()
                line_items.append({"description": description, "price": price})

            current_block = [] # Reset for the next item

    parsed_data["line_items"] = line_items
    
    # --- Final fallback for total if keyword search failed ---
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
