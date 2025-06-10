import streamlit as st
from google.cloud import vision
import re
from itertools import combinations
import fitz  # PyMuPDF for PDF handling
import io
from PIL import Image

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
    Extracts text from an image or PDF file using Google Cloud Vision AI.
    If the file is a PDF, it converts each page to an image before sending.
    """
    client = get_vision_client()
    file_bytes = uploaded_file.getvalue()
    mime_type = uploaded_file.type
    
    try:
        # If it's a PDF, process page by page
        if mime_type == "application/pdf":
            full_text = ""
            with fitz.open(stream=file_bytes, filetype="pdf") as doc:
                for page_num, page in enumerate(doc):
                    # Render page to a high-quality PNG image in memory
                    pix = page.get_pixmap(dpi=300)
                    img_bytes = pix.tobytes("png")
                    
                    image = vision.Image(content=img_bytes)
                    response = client.document_text_detection(image=image)
                    if response.error.message:
                        raise Exception(f"Google Vision API error on page {page_num+1}: {response.error.message}")
                    
                    full_text += response.full_text_annotation.text + "\n"
            return full_text
        
        # If it's an image, send it directly
        elif mime_type in ["image/png", "image/jpeg", "image/jpg"]:
            image = vision.Image(content=file_bytes)
            response = client.document_text_detection(image=image)
            if response.error.message:
                raise Exception(response.error.message)
            return response.full_text_annotation.text
        
        else:
            return "Unsupported file type. Please upload a JPG, PNG, or PDF."

    except Exception as e:
        return f"Error calling Google Vision API: {str(e)}. Please ensure the uploaded file is not corrupted."

# --- DEFINITIVE PARSING LOGIC: RIGHT-TO-LEFT ---
def parse_ocr_text(text: str):
    """Parses OCR text using targeted, line-by-line regular expressions."""
    parsed_data = {"vendor": "N/A", "date": "N/A", "total_amount": 0.0, "gst_amount": 0.0, "pst_amount": 0.0, "hst_amount": 0.0, "line_items": []}
    lines = [line.strip() for line in text.split('\n') if line.strip()]

    # Keyword Definitions
    total_keywords = ["total"]
    subtotal_keywords = ["sous-total", "subtotal", "total partiel"]
    gst_keywords = ["tps", "gst", "federal tax", "taxe fédérale"]
    pst_keywords = ["tvq", "qst", "tvp", "pst", "provincial tax", "taxe provinciale"]
    hst_keywords = ["hst", "tvh"]
    
    # Line-by-Line Classification
    line_pattern = re.compile(r'^(.*?)\s*[$]?(\d+[.,]\d{2})[$]?\s*$', re.IGNORECASE)

    for line in lines:
        if match := line_pattern.match(line):
            description = match.group(1).strip()
            price_str = match.group(2).replace(',', '.')
            price = float(price_str)
            desc_lower = description.lower()

            if re.search(r'(?<!sous-)(?<!sub)total', desc_lower):
                parsed_data['total_amount'] = price
            elif any(kw in desc_lower for kw in gst_keywords):
                parsed_data['gst_amount'] = price
            elif any(kw in desc_lower for kw in pst_keywords):
                parsed_data['pst_amount'] = price
            elif any(kw in desc_lower for kw in hst_keywords):
                parsed_data['hst_amount'] = price
            elif any(kw in desc_lower for kw in subtotal_keywords):
                pass
            else:
                if len(description) > 1 and "merci" not in desc_lower and "approved" not in desc_lower:
                    parsed_data["line_items"].append({'description': description, 'price': price})

    # Vendor and Date Post-Processing
    if lines:
        for line in lines[:5]:
            if len(line) > 3 and line.upper() == line and not any(kw in line.lower() for kw in ["invoice", "facture", "date", "caissier", "transaction"]):
                parsed_data["vendor"] = line
                break
    
    date_pattern = r'(\d{4}[-/\s]\d{1,2}[-/\s]\d{1,2})'
    if date_match := re.search(date_pattern, text):
        parsed_data["date"] = date_match.group(1).strip()

    return parsed_data

# --- Main Entry Point Function ---
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
