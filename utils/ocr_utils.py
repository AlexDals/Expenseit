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

# --- HELPER FUNCTIONS FOR NEW PARSING LOGIC ---
def _find_grand_total(text, all_numbers):
    keywords = ["total payable", "total à payer", "invoice total"]
    ignore_keywords = ["subtotal", "partiel"]
    
    for line in text.split('\n'):
        line_lower = line.lower()
        if any(kw in line_lower for kw in keywords) and not any(ikw in line_lower for ikw in ignore_keywords):
            amounts_on_line = [float(m.group(1).replace(',', '.')) for m in re.finditer(r'[$€£]?\s*(\d+[.,]\d{2})', line)]
            if amounts_on_line:
                return max(amounts_on_line)
    
    return max(all_numbers) if all_numbers else 0.0

def _find_subtotal(text, all_numbers, grand_total):
    keywords = ["subtotal", "sous-total", "total partiel"]
    
    # Find the largest number on a "subtotal" line that is NOT the grand total
    candidates = []
    for line in text.split('\n'):
        if any(kw in line.lower() for kw in keywords):
            amounts_on_line = [float(m.group(1).replace(',', '.')) for m in re.finditer(r'[$€£]?\s*(\d+[.,]\d{2})', line)]
            for amount in amounts_on_line:
                if amount != grand_total:
                    candidates.append(amount)
    if candidates:
        return max(candidates)

    # Fallback: Find the largest number that is smaller than the grand total
    smaller_numbers = [n for n in all_numbers if n < grand_total]
    return max(smaller_numbers) if smaller_numbers else 0.0

# --- FINAL, DEFINITIVE PARSING LOGIC ---
def parse_ocr_text(text: str):
    parsed_data = {
        "vendor": "N/A", "date": "N/A", "total_amount": 0.0,
        "gst_amount": 0.0, "pst_amount": 0.0, "hst_amount": 0.0,
    }

    # --- Stage 1: Basic Field Extraction ---
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    if lines:
        for line in lines:
            if line.lower().startswith("sold by / vendu par:"):
                parsed_data["vendor"] = line.split(":", 1)[1].strip()
                break
        if parsed_data["vendor"] == "N/A" and len(lines[0]) < 50:
            parsed_data["vendor"] = lines[0]

    date_pattern = r'(?i)(?:Date|Invoice Date)[:\s]*(\d{1,2}[-/.\s]+\w+[-/.\s]+\d{2,4}|\w+[-/.\s]+\d{1,2}[,.\s]+\d{2,4}|\d{4}[-/]\d{2}[-/]\d{2}|\d{2}[-/]\d{2}[-/]\d{4})'
    date_match = re.search(date_pattern, text)
    if date_match: parsed_data["date"] = date_match.group(1).strip()

    # --- Stage 2: Find Anchors and All Numbers ---
    all_numbers = [float(m.group(1).replace(',', '.')) for m in re.finditer(r'[$€£]?\s*(\d+[.,]\d{2})', text)]
    grand_total = _find_grand_total(text, all_numbers)
    subtotal = _find_subtotal(text, all_numbers, grand_total)
    
    parsed_data["total_amount"] = grand_total

    # --- Stage 3: Mathematical Validation ---
    tax_candidates = [n for n in all_numbers if n not in [grand_total, subtotal] and 0 < n < grand_total]
    validated_taxes = []

    if subtotal > 0 and grand_total > subtotal and tax_candidates:
        # Look for combinations of 1 or 2 taxes
        for i in range(1, 3): 
            for combo in combinations(tax_candidates, i):
                if abs((subtotal + sum(combo)) - grand_total) < 0.02: # 2 cent tolerance
                    validated_taxes = sorted(list(combo))
                    break
            if validated_taxes:
                break
    
    # --- Stage 4: Label Validated Taxes ---
    if validated_taxes:
        hst_keywords = ["hst", "tvh"]
        # Check for HST first as it's usually a single, larger tax
        if len(validated_taxes) == 1 and any(keyword in text.lower() for keyword in hst_keywords):
            parsed_data["hst_amount"] = validated_taxes[0]
        else:
            # Assume smaller tax is GST, larger is PST for 2-tax scenarios
            if len(validated_taxes) >= 1:
                parsed_data["gst_amount"] = validated_taxes[0]
            if len(validated_taxes) >= 2:
                parsed_data["pst_amount"] = validated_taxes[1]

    return parsed_data

# --- Main Entry Point Function (No changes needed, but included for completeness) ---
def extract_and_parse_file(uploaded_file):
    try:
        text_content = extract_text_from_file(uploaded_file)
        if "Error" in text_content or "Unsupported" in text_content:
             return {"error": text_content}
        return parse_ocr_text(text_content)
    except Exception as e:
        return {"error": f"A critical error occurred in the OCR pipeline: {str(e)}"}
