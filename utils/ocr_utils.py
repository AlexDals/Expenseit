import streamlit as st
from google.cloud import vision
import re
from itertools import combinations
import fitz  # PyMuPDF
import io
from PIL import Image
import cv2   # OpenCV for image processing
import numpy as np


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

# --- UNIVERSAL IMAGE PREPROCESSOR ---
def preprocess_image(image_bytes):
    """
    Takes any image bytes and converts them into a clean, high-contrast
    black and white image suitable for OCR.
    """
    try:
        img_array = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        # Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        # Apply a threshold to get a black and white image
        # Otsu's binarization is great for automatically finding the best threshold
        _, final_img = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        # Encode the processed image back to PNG bytes
        _, processed_img_bytes = cv2.imencode('.png', final_img)
        return processed_img_bytes.tobytes()
    except Exception as e:
        # If preprocessing fails, return original bytes and hope for the best
        st.warning(f"Image preprocessing failed: {e}. Using original image data.")
        return image_bytes

# --- DEFINITIVE FILE EXTRACTION LOGIC ---
def extract_text_from_file(uploaded_file):
    """
    Extracts text from an image or PDF file using Google Cloud Vision AI.
    It ensures all inputs are converted to clean images before being sent to the API.
    """
    client = get_vision_client()
    file_bytes = uploaded_file.getvalue()
    mime_type = uploaded_file.type
    
    try:
        # If it's a PDF, convert each page to a preprocessed image
        if mime_type == "application/pdf":
            full_text = ""
            with fitz.open(stream=file_bytes, filetype="pdf") as doc:
                for page_num, page in enumerate(doc):
                    pix = page.get_pixmap(dpi=300)
                    img_bytes = pix.tobytes("png")
                    
                    # Preprocess the rendered page image
                    processed_bytes = preprocess_image(img_bytes)
                    
                    image = vision.Image(content=processed_bytes)
                    response = client.document_text_detection(image=image)
                    if response.error.message:
                        raise Exception(f"Google Vision API error on page {page_num+1}: {response.error.message}")
                    
                    full_text += response.full_text_annotation.text + "\n"
            return full_text
        
        # If it's an image, preprocess it before sending
        elif mime_type in ["image/png", "image/jpeg", "image/jpg"]:
            processed_bytes = preprocess_image(file_bytes)
            image = vision.Image(content=processed_bytes)
            response = client.document_text_detection(image=image)
            if response.error.message:
                raise Exception(response.error.message)
            return response.full_text_annotation.text
        
        else:
            return "Unsupported file type. Please upload a JPG, PNG, or PDF."

    except Exception as e:
        return f"Error calling Google Vision API: {str(e)}. Please ensure the uploaded file is not corrupted."

# --- PARSING LOGIC (This is our stable 'Right-to-Left' parser) ---
def parse_ocr_text(text: str):
    parsed_data = {"vendor": "N/A", "date": "N/A", "total_amount": 0.0, "gst_amount": 0.0, "pst_amount": 0.0, "hst_amount": 0.0, "line_items": []}
    lines = [line.strip() for line in text.split('\n') if line.strip()]

    total_keywords = ["total"]
    subtotal_keywords = ["sous-total", "subtotal", "total partiel"]
    gst_keywords = ["tps", "gst", "federal tax", "taxe fédérale"]
    pst_keywords = ["tvq", "qst", "tvp", "pst", "provincial tax", "taxe provinciale"]
    hst_keywords = ["hst", "tvh"]
    
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
    try:
        raw_text = extract_text_from_file(uploaded_file)
        if "Error" in raw_text:
             return raw_text, {"error": raw_text}
        
        parsed_data = parse_ocr_text(raw_text)
        return raw_text, parsed_data
    except Exception as e:
        error_message = f"A critical error occurred: {str(e)}"
        return error_message, {"error": error_message}
