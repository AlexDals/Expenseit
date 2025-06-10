import pytesseract
from PIL import Image
import io
import re
import fitz  # PyMuPDF
import cv2  # OpenCV
import numpy as np
from itertools import combinations
import streamlit as st

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
        resized = cv2.resize(gray, dim, interpolation=cv2.INTER_CUBIC)

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
    try:
        file_bytes = uploaded_file.getvalue()
        full_text = ""
        custom_config = r'--oem 3 --psm 4'
        if uploaded_file.type == "application/pdf":
            with fitz.open(stream=file_bytes, filetype="pdf") as doc:
                for page in doc:
                    pix = page.get_pixmap(dpi=300)
                    processed_bytes = preprocess_image_for_ocr(pix.tobytes("png"))
                    full_text += pytesseract.image_to_string(Image.open(io.BytesIO(processed_bytes)), config=custom_config) + "\n"
            return full_text
        elif uploaded_file.type in ["image/png", "image/jpeg", "image/jpg"]:
            processed_bytes = preprocess_image_for_ocr(file_bytes)
            return pytesseract.image_to_string(Image.open(io.BytesIO(processed_bytes)), config=custom_config)
        return "Unsupported file type."
    except Exception as e:
        return f"Error during OCR processing: {str(e)}"

def parse_ocr_text(text: str):
    """Parses OCR text using targeted, line-by-line regular expressions."""
    parsed_data = {"vendor": "N/A", "date": "N/A", "total_amount": 0.0, "gst_amount": 0.0, "pst_amount": 0.0, "hst_amount": 0.0, "line_items": []}
    lines = [line.strip() for line in text.split('\n') if line.strip()]

    if lines:
        for line in lines[:5]:
            if len(line) > 3 and line.upper() == line and not any(kw in line.lower() for kw in ["invoice", "facture", "date", "caissier", "transaction"]):
                parsed_data["vendor"] = line
                break
    
    date_pattern = r'(\d{4}[-/\s]\d{1,2}[-/\s]\d{1,2})'
    if date_match := re.search(date_pattern, text):
        parsed_data["date"] = date_match.group(1).strip()
    
    all_amounts = sorted(list(set([float(m.replace(',', '.')) for m in re.findall(r'(\d+[.,]\d{2})', text)])), reverse=True)
    
    if len(all_amounts) >= 2:
        grand_total = all_amounts[0]
        parsed_data["total_amount"] = grand_total
        
        subtotal = 0.0
        subtotal_keywords = ["sous-total", "subtotal"]
        for line in lines:
            if any(kw in line.lower() for kw in subtotal_keywords):
                if line_amounts := [float(m.replace(',', '.')) for m in re.findall(r'(\d+[.,]\d{2})', line)]:
                    subtotal = max(line_amounts)
                    break
        
        if subtotal == 0.0 and len(all_amounts) > 1:
            subtotal = all_amounts[1]
        
        expected_tax_sum = round(grand_total - subtotal, 2)
        if expected_tax_sum > 0:
            tax_candidates = [amt for amt in all_amounts if amt < subtotal and abs(amt - expected_tax_sum) > 0.01]
            validated_taxes = []
            for i in range(1, 4):
                for combo in combinations(tax_candidates, i):
                    if abs(sum(combo) - expected_tax_sum) < 0.02:
                        validated_taxes = sorted(list(combo))
                        break
                if validated_taxes:
                    break
            
            if validated_taxes:
                if len(validated_taxes) == 1:
                    parsed_data["hst_amount"] = validated_taxes[0]
                elif len(validated_taxes) >= 2:
                    parsed_data["gst_amount"] = validated_taxes[0]
                    parsed_data["pst_amount"] = validated_taxes[1]

    line_items = []
    current_description_lines = []
    stop_keywords = ["ecofrais", "sous-total", "subtotal", "tax", "tps", "tvq", "gst", "pst", "hst"]
    start_index = 0
    for i, line in enumerate(lines):
        if any(kw in line.lower() for kw in ["description", "quantit", "price", "prix"]):
            start_index = i + 1
            break
            
    price_pattern = re.compile(r'([\d.,]+\d{2})$')

    for line in lines[start_index:]:
        line_lower = line.lower()
        if any(keyword in line_lower for keyword in stop_keywords):
            break

        match = price_pattern.search(line)
        
        description_part = line[:match.start()].strip() if match else line
        
        if match:
            price = float(match.group(1).replace(',', '.'))
            if description_part:
                current_description_lines.append(description_part)
            
            if current_description_lines:
                full_description = " ".join(current_description_lines)
                line_items.append({"description": full_description, "price": price})
            
            current_description_lines = []
        else:
            if len(line.strip()) > 1:
                current_description_lines.append(line.strip())

    parsed_data["line_items"] = line_items
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
