import pytesseract
from PIL import Image
import io
import re
import fitz  # PyMuPDF
import cv2  # OpenCV
import numpy as np
from google.cloud import vision
import streamlit as st

# --- GOOGLE VISION API AND IMAGE PREPROCESSING (No changes) ---
@st.cache_resource
def get_vision_client():
    try:
        credentials_dict = dict(st.secrets.google_credentials)
        client = vision.ImageAnnotatorClient.from_service_account_info(credentials_dict)
        return client
    except Exception as e:
        st.error(f"Could not initialize Google Vision API client: {e}. Please check your Streamlit secrets.")
        st.stop()

def preprocess_image_for_ocr(image_bytes):
    try:
        img_array = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        scale_percent = 200
        width = int(img.shape[1] * scale_percent / 100)
        height = int(img.shape[0] * scale_percent / 100)
        dim = (width, height)
        resized = cv2.resize(gray, dim, interpolation = cv2.INTER_CUBIC)
        _, final_img = cv2.threshold(resized, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        _, processed_img_bytes = cv2.imencode('.png', final_img)
        return processed_img_bytes.tobytes()
    except Exception:
        img_array = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
        _, processed_img_bytes = cv2.imencode('.png', thresh)
        return processed_img_bytes.tobytes()


def extract_text_from_file(uploaded_file):
    client = get_vision_client()
    file_bytes = uploaded_file.getvalue()
    try:
        if uploaded_file.type == "application/pdf":
            full_text = ""
            with fitz.open(stream=file_bytes, filetype="pdf") as doc:
                for page in doc:
                    pix = page.get_pixmap(dpi=300)
                    processed_bytes = preprocess_image_for_ocr(pix.tobytes("png"))
                    image = vision.Image(content=processed_bytes)
                    response = client.document_text_detection(image=image)
                    if response.error.message: raise Exception(response.error.message)
                    full_text += response.full_text_annotation.text + "\n"
            return full_text
        elif uploaded_file.type in ["image/png", "image/jpeg", "image/jpg"]:
            processed_bytes = preprocess_image_for_ocr(file_bytes)
            image = vision.Image(content=processed_bytes)
            response = client.document_text_detection(image=image)
            if response.error.message: raise Exception(response.error.message)
            return response.full_text_annotation.text
        return "Unsupported file type."
    except Exception as e:
        return f"Error calling Google Vision API: {str(e)}"

# --- DEFINITIVE PARSING LOGIC: RIGHT-TO-LEFT ---
def parse_ocr_text(text: str):
    parsed_data = {"vendor": "N/A", "date": "N/A", "total_amount": 0.0, "gst_amount": 0.0, "pst_amount": 0.0, "hst_amount": 0.0, "line_items": []}
    lines = [line.strip() for line in text.split('\n') if line.strip()]

    # --- Keyword Definitions ---
    total_keywords = ["total"]
    subtotal_keywords = ["sous-total", "subtotal", "total partiel"]
    gst_keywords = ["tps", "gst", "federal tax", "taxe fédérale"]
    pst_keywords = ["tvq", "qst", "tvp", "pst", "provincial tax", "taxe provinciale"]
    hst_keywords = ["hst", "tvh"]
    
    # --- Line-by-Line Classification ---
    # Pattern to capture a description part (group 1) and a price on the right (group 2)
    line_pattern = re.compile(r'^(.*?)\s*([$]?\d+[.,]\d{2})$')

    for line in lines:
        if match := line_pattern.match(line):
            description = match.group(1).strip()
            price_str = match.group(2).replace('$', '').replace(',', '.')
            price = float(price_str)
            desc_lower = description.lower()

            # Use a negative lookbehind `(?<!...)` to find "total" but not "subtotal"
            if re.search(r'(?i)(?<!sous-)(?<!sub)total', desc_lower):
                parsed_data['total_amount'] = price
            elif any(kw in desc_lower for kw in gst_keywords):
                parsed_data['gst_amount'] = price
            elif any(kw in desc_lower for kw in pst_keywords):
                parsed_data['pst_amount'] = price
            elif any(kw in desc_lower for kw in hst_keywords):
                parsed_data['hst_amount'] = price
            elif any(kw in desc_lower for kw in subtotal_keywords):
                # We note the subtotal but don't add it as a line item
                pass
            else:
                # If no financial keywords match, it's a line item
                if len(description) > 1 and "merci" not in desc_lower and "approved" not in desc_lower:
                    parsed_data["line_items"].append({'description': description, 'price': price})

    # --- Vendor and Date Post-Processing ---
    if lines:
        for line in lines[:5]:
            # A good vendor name is often capitalized and doesn't contain digits or common receipt words
            if len(line) > 3 and line.upper() == line and not any(char.isdigit() for char in line) and not any(kw in line.lower() for kw in ["invoice", "facture", "date", "caissier"]):
                parsed_data["vendor"] = line
                break
    
    date_pattern = r'(\d{4}[-/\s]\d{1,2}[-/\s]\d{1,2})'
    if date_match := re.search(date_pattern, text):
        parsed_data["date"] = date_match.group(1).strip()

    return parsed_data

def extract_and_parse_file(uploaded_file):
    """Main pipeline function."""
    try:
        raw_text = extract_text_from_file(uploaded_file)
        if "Error" in raw_text or "Unsupported" in raw_text:
             return raw_text, {"error": raw_text}
        parsed_data = parse_ocr_text(raw_text)
        return raw_text, parsed_data
    except Exception as e:
        error_message = f"A critical error occurred: {str(e)}"
        return error_message, {"error": error_message}
