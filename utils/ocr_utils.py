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

# --- DEFINITIVE FILE EXTRACTION LOGIC ---
def extract_text_from_file(uploaded_file):
    """
    Extracts text from an image or PDF file by sending the raw bytes directly
    to the robust Google Vision batch processing endpoint.
    """
    client = get_vision_client()
    file_bytes = uploaded_file.getvalue()
    mime_type = uploaded_file.type
    
    try:
        # Create an Image object from the raw bytes of the uploaded file.
        image = vision.Image(content=file_bytes)
        
        # Specify the feature we want (document text detection).
        feature = vision.Feature(type_=vision.Feature.Type.DOCUMENT_TEXT_DETECTION)
        
        # Construct the request. For PDFs, the API handles page separation automatically.
        request = vision.AnnotateImageRequest(image=image, features=[feature])
        
        # Use the more robust batch_annotate_images method.
        response = client.batch_annotate_images(requests=[request])
        
        # Process the response
        # The response is a list, one for each image/document in the batch. We only have one.
        document_response = response.responses[0]
        if document_response.error.message:
            raise Exception(f"{document_response.error.message}")
            
        return document_response.full_text_annotation.text

    except Exception as e:
        return f"Error calling Google Vision API: {str(e)}. Please ensure the PDF is not password-protected or corrupted."

# --- DEFINITIVE PARSING LOGIC ---
def parse_ocr_text(text: str):
    """Parses OCR text using a robust 'Right-to-Left' classification and a smart 'Look-Back' cleanup pass."""
    parsed_data = {"vendor": "N/A", "date": "N/A", "total_amount": 0.0, "gst_amount": 0.0, "pst_amount": 0.0, "hst_amount": 0.0, "line_items": []}
    lines = [line.strip() for line in text.split('\n') if line.strip()]

    # Stage 1: Basic Vendor and Date Extraction
    if lines:
        for line in lines[:5]:
            if len(line) > 3 and line.upper() == line and not any(kw in line.lower() for kw in ["invoice", "facture", "date", "caissier"]):
                parsed_data["vendor"] = line
                break
    
    date_pattern = r'(\d{4}[-/\s]\d{1,2}[-/\s]\d{1,2})|(\d{1,2}[-/\s]\d{1,2}[-/\s]\d{2,4})'
    if date_match := re.search(date_pattern, text):
        parsed_data["date"] = date_match.group(0).strip()

    # Stage 2: Classify all lines that end with a price
    classified_items = []
    line_pattern = re.compile(r'^(.*?)\s*([$]?\d+[.,]\d{2})[$]?\s*$')

    total_keywords = ["total"]
    subtotal_keywords = ["sous-total", "subtotal"]
    gst_keywords = ["tps", "gst"]
    pst_keywords = ["tvq", "qst", "pst"]
    hst_keywords = ["hst", "tvh"]

    for i, line in enumerate(lines):
        match = line_pattern.match(line)
        if not match:
            continue

        description = match.group(1).strip()
        price = float(match.group(2).replace('$', '').replace(',', '.'))
        desc_lower = description.lower()
        
        item_type = 'item' 
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

    # Stage 3: Assign Financials and intelligently process Line Items
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
            
    final_line_items = []
    item_only_list = sorted([item for item in classified_items if item['type'] == 'item'], key=lambda x: x['index'])
    
    for i, current_item in enumerate(item_only_list):
        description_block_lines = [current_item['description']]
        previous_item_index = item_only_list[i-1]['index'] if i > 0 else -1
        lookup_index = current_item['index'] - 1

        while lookup_index > previous_item_index:
            description_block_lines.insert(0, lines[lookup_index])
            lookup_index -= 1
        
        full_description = " ".join(filter(None, description_block_lines)).strip()
        
        if full_description:
             final_line_items.append({'description': full_description, 'price': current_item['price']})

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
