import pytesseract
from PIL import Image
import io
import re
import fitz  # PyMuPDF
import cv2  # OpenCV
import numpy as np
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

# --- FINAL PARSING LOGIC v8 ---
def _find_amount_from_lines(lines, keywords):
    """Helper to find the first amount on a line matching keywords, searching backwards."""
    for line in reversed(lines):
        if any(keyword in line.lower() for keyword in keywords):
            # Find the largest number on that line
            amounts = [float(m.replace(',', '.')) for m in re.findall(r'(\d+[.,]\d{2})', line)]
            if amounts:
                return max(amounts)
    return 0.0

def parse_ocr_text(text: str):
    parsed_data = {
        "vendor": "N/A", "date": "N/A", "total_amount": 0.0,
        "gst_amount": 0.0, "pst_amount": 0.0, "hst_amount": 0.0,
    }

    lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    # --- Stage 1: Basic Field Extraction ---
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

    # --- Stage 2: Find Anchors (Total and Subtotal) using Reverse Search ---
    total_keywords = ["total payable", "total à payer", "invoice total"]
    subtotal_keywords = ["subtotal", "sous-total", "total partiel"]
    
    grand_total = _find_amount_from_lines(lines, total_keywords)
    subtotal = _find_amount_from_lines(lines, subtotal_keywords)
    
    all_numbers = [float(m.replace(',', '.')) for m in re.findall(r'(\d+[.,]\d{2})', text)]
    if grand_total == 0.0 and all_numbers: grand_total = max(all_numbers)
    # If subtotal logic picked up the grand total, find the next largest number
    if subtotal == grand_total and all_numbers:
        smaller_numbers = sorted([n for n in all_numbers if n < grand_total], reverse=True)
        if smaller_numbers:
            subtotal = smaller_numbers[0]

    parsed_data["total_amount"] = grand_total

    # --- Stage 3: Mathematical Validation ---
    tax_candidates = sorted([n for n in all_numbers if n not in [grand_total, subtotal] and 0 < n < subtotal], reverse=True)
    validated_taxes = []

    if subtotal > 0 and grand_total > subtotal and tax_candidates:
        for i in range(1, 4): # Look for combinations of 1, 2, or 3 taxes
            for combo in combinations(tax_candidates, i):
                if abs((subtotal + sum(combo)) - grand_total) < 0.02:
                    validated_taxes = sorted(list(combo))
                    break
            if validated_taxes:
                break

    # --- Stage 4: Label Validated Taxes ---
    if validated_taxes:
        # For now, use a simple heuristic: smallest is GST, next is PST.
        # This can be improved later with positional context if needed.
        if len(validated_taxes) == 1:
            parsed_data["hst_amount"] = validated_taxes[0]
        if len(validated_taxes) >= 1:
            parsed_data["gst_amount"] = validated_taxes.pop(0)
        if len(validated_taxes) >= 1:
            parsed_data["pst_amount"] = validated_taxes.pop(0)
            
    return parsed_data

# --- Main Entry Point Function (UPDATED) ---
def extract_and_parse_file(uploaded_file):
    """
    Orchestrates OCR and parsing. Now returns both raw text and parsed data.
    """
    try:
        raw_text = extract_text_from_file(uploaded_file)
        if "Error" in raw_text or "Unsupported" in raw_text:
             return raw_text, {"error": raw_text}
        
        parsed_data = parse_ocr_text(raw_text)
        return raw_text, parsed_data # Return both
        
    except Exception as e:
        error_message = f"A critical error occurred in the OCR pipeline: {str(e)}"
        return error_message, {"error": error_message}
