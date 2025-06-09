import pytesseract
from PIL import Image
import io
import re
import fitz  # PyMuPDF
import cv2  # OpenCV
import numpy as np
import pandas as pd
from itertools import combinations

# --- IMAGE PREPROCESSING AND TEXT EXTRACTION (No changes) ---
def preprocess_image(image_bytes):
    img_array = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                   cv2.THRESH_BINARY, 11, 2)
    _, processed_img_bytes = cv2.imencode('.png', thresh)
    return processed_img_bytes.tobytes()

def extract_text_from_file(uploaded_file):
    try:
        file_bytes = uploaded_file.getvalue()
        full_text = ""
        custom_config = r'--oem 3 --psm 4'
        if uploaded_file.type == "application/pdf":
            with fitz.open(stream=file_bytes, filetype="pdf") as doc:
                for page_num, page in enumerate(doc):
                    pix = page.get_pixmap(dpi=300)
                    img_bytes = pix.tobytes("png")
                    processed_bytes = preprocess_image(img_bytes)
                    image = Image.open(io.BytesIO(processed_bytes))
                    page_text = pytesseract.image_to_string(image, config=custom_config)
                    full_text += page_text + f"\n--- Page {page_num+1} ---\n"
            return full_text
        elif uploaded_file.type in ["image/png", "image/jpeg", "image/jpg"]:
            processed_bytes = preprocess_image(file_bytes)
            image = Image.open(io.BytesIO(processed_bytes))
            return pytesseract.image_to_string(image, config=custom_config)
        else:
            return "Unsupported file type."
    except Exception as e:
        return f"Error during OCR processing: {str(e)}"

# --- FINAL MATHEMATICAL PARSING LOGIC ---
def _find_amount_from_lines(lines, keywords):
    """Helper to find the first amount on a line matching keywords, searching backwards."""
    for line in reversed(lines):
        if any(keyword in line.lower() for keyword in keywords):
            amounts_on_line = [float(m.replace(',', '.')) for m in re.findall(r'(\d+[.,]\d{2})', line)]
            if amounts_on_line:
                return max(amounts_on_line)
    return 0.0

def parse_ocr_text(text: str):
    parsed_data = {
        "vendor": "N/A", "date": "N/A", "total_amount": 0.0,
        "gst_amount": 0.0, "pst_amount": 0.0, "hst_amount": 0.0,
    }

    lines = [line.strip() for line in text.split('\n') if line.strip()]
    if lines:
        for line in lines:
            if line.lower().startswith("sold by / vendu par:"):
                parsed_data["vendor"] = line.split(":", 1)[1].strip()
                break
        if parsed_data["vendor"] == "N/A" and len(lines[0]) < 50:
            parsed_data["vendor"] = lines[0]

    date_pattern = r'(?i)(?:Date|Invoice Date)[:\s]*(\d{1,2}[-/.\s]+\w+[-/.\s]+\d{2,4}|\w+[-/.\s]+\d{1,2}[,.\s]+\d{2,4})'
    date_match = re.search(date_pattern, text)
    if date_match: parsed_data["date"] = date_match.group(1).strip()

    all_amounts = sorted(list(set([float(m.replace(',', '.')) for m in re.findall(r'(\d+[.,]\d{2})', text)])), reverse=True)
    
    if len(all_amounts) >= 2:
        grand_total = all_amounts[0]
        subtotal = all_amounts[1]
        parsed_data["total_amount"] = grand_total
        
        expected_tax_sum = round(grand_total - subtotal, 2)
        tax_candidates = [amt for amt in all_amounts if amt < subtotal and abs(amt - expected_tax_sum) > 0.01]
        
        validated_taxes = []
        for i in range(1, len(tax_candidates) + 1):
            for combo in combinations(tax_candidates, i):
                if abs(sum(combo) - expected_tax_sum) < 0.02:
                    validated_taxes = sorted(list(combo))
                    break
            if validated_taxes:
                break
        
        if validated_taxes:
            if len(validated_taxes) == 1:
                if any(keyword in text.lower() for keyword in ["hst", "tvh"]):
                     parsed_data["hst_amount"] = validated_taxes[0]
                else:
                     parsed_data["gst_amount"] = validated_taxes[0]
            elif len(validated_taxes) >= 2:
                parsed_data["gst_amount"] = validated_taxes[0]
                parsed_data["pst_amount"] = validated_taxes[1]

    return parsed_data

# --- Main Entry Point Function ---
def extract_and_parse_file(uploaded_file):
    """
    Orchestrates OCR and parsing. 
    NOTE: This function now reliably returns a tuple of two values: (raw_text, parsed_data)
    """
    try:
        raw_text = extract_text_from_file(uploaded_file)
        # Handle cases where text extraction itself fails
        if "Error" in raw_text or "Unsupported" in raw_text:
             return raw_text, {"error": raw_text}
        
        # Proceed with parsing if text extraction was successful
        parsed_data = parse_ocr_text(raw_text)
        return raw_text, parsed_data
        
    except Exception as e:
        error_message = f"A critical error occurred in the OCR pipeline: {str(e)}"
        # Ensure two values are returned even in a critical failure
        return error_message, {"error": error_message}
