import pytesseract
from PIL import Image
import io
import re
import fitz  # PyMuPDF
import cv2  # OpenCV
import numpy as np
from google.cloud import vision
import streamlit as st

# --- GOOGLE VISION API SETUP AND PREPROCESSING ---
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

def preprocess_image_for_ocr(image_bytes):
    """Advanced preprocessing with resizing and thresholding."""
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
    """Extracts text from file using OCR."""
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

# --- DEFINITIVE PARSING LOGIC: BLOCK-AWARE ---
def parse_ocr_text(text: str):
    parsed_data = {"vendor": "N/A", "date": "N/A", "total_amount": 0.0, "gst_amount": 0.0, "pst_amount": 0.0, "hst_amount": 0.0, "line_items": []}
    lines = [line.strip() for line in text.split('\n') if line.strip()]

    # --- Regex Definitions ---
    price_pattern = re.compile(r'(\d+[.,]\d{2})$')
    date_pattern = re.compile(r'(\d{2,4}[-/\s]\d{1,2}[-/\s]\d{1,2})')
    
    # --- Data Extraction Pass ---
    current_description_lines = []
    stop_keywords = ["sous-total", "subtotal"]

    for i, line in enumerate(lines):
        line_lower = line.lower()
        
        # Stop processing for line items when we hit the subtotal section
        if any(keyword in line_lower for keyword in stop_keywords):
            break

        # Check if the line is JUST a price, which belongs to the previous description block
        if match := price_pattern.match(line.replace('$', '').strip()):
            if current_description_lines:
                price = float(match.group(1).replace(',', '.'))
                full_description = " ".join(current_description_lines)
                parsed_data["line_items"].append({"description": full_description, "price": price})
                current_description_lines = [] # Reset after creating an item
            continue

        # Check if the line contains text AND a price (single-line item)
        match = re.match(r'^(.*?)\s+([\d.,]+\d{2})$', line)
        if match:
            description, price_str = match.groups()
            price = float(price_str.replace(',', '.'))
            
            # If there was a description building up, finalize it first
            if current_description_lines:
                full_description = " ".join(current_description_lines)
                # Heuristic: if the price of the previous block is missing, this price might belong to it
                # This part is complex, for now we assume price ends the block.
                # A simpler logic is to just add the pending block as an item without a price.
                # For now, we will associate this price with this line's description.
                
            # Add the current line as a new item
            parsed_data["line_items"].append({"description": description.strip(), "price": price})
            current_description_lines = [] # Reset
            continue
            
        # If no price found, it's part of a description block
        if len(line) > 1:
            current_description_lines.append(line)

    # --- Post-process the entire text for summary financials ---
    for line in lines:
        line_lower = line.lower()
        if 'total' in line_lower and 'sous-total' not in line_lower and 'subtotal' not in line_lower:
            if amounts := re.findall(r'(\d+[.,]\d{2})', line):
                parsed_data['total_amount'] = max([float(a.replace(',', '.')) for a in amounts])
        elif any(kw in line_lower for kw in ['tps', 'gst']):
            if amounts := re.findall(r'(\d+[.,]\d{2})', line):
                parsed_data['gst_amount'] = float(amounts[0].replace(',', '.'))
        elif any(kw in line_lower for kw in ['tvq', 'qst', 'pst']):
            if amounts := re.findall(r'(\d+[.,]\d{2})', line):
                parsed_data['pst_amount'] = float(amounts[0].replace(',', '.'))

    # --- Vendor and Date Extraction ---
    if lines:
        for line in lines[:5]:
            if len(line) > 2 and line.upper() == line and not any(kw in line.lower() for kw in ["invoice", "facture", "date", "caissier"]):
                parsed_data["vendor"] = line
                break
    
    if date_match := re.search(date_pattern, text):
        parsed_data["date"] = date_match.group(1).strip()
    
    # Final check: If total is still zero, use the largest number
    if parsed_data["total_amount"] == 0.0:
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
