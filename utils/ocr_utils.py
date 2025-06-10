import pytesseract
from PIL import Image
import io
import re
import fitz  # PyMuPDF
import cv2  # OpenCV
import numpy as np
from itertools import combinations

def preprocess_image_for_ocr(image_bytes):
    """Advanced preprocessing with perspective correction."""
    try:
        img_array = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        # Increase scale for better detail recognition
        width = int(img.shape[1] * 2)
        height = int(img.shape[0] * 2)
        resized = cv2.resize(gray, (width, height), interpolation=cv2.INTER_CUBIC)
        _, final_img = cv2.threshold(resized, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        _, processed_img_bytes = cv2.imencode('.png', final_img)
        return processed_img_bytes.tobytes()
    except Exception:
        # Fallback to a simpler method if advanced processing fails
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
        # PSM 6 is generally better for blocks of text like receipts
        custom_config = r'--oem 3 --psm 6'
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
    """Parses OCR text using the 'Numbers First' mathematical deduction method."""
    parsed_data = {"vendor": "N/A", "date": "N/A", "total_amount": 0.0, "gst_amount": 0.0, "pst_amount": 0.0, "hst_amount": 0.0, "line_items": []}
    lines = [line.strip() for line in text.split('\n') if line.strip()]

    # --- Stage 1: Basic Vendor and Date Extraction ---
    if lines:
        vendor_candidates = []
        for line in lines[:5]: # Check top 5 lines
            # A good vendor name is usually short, capitalized, and has no digits.
            if len(line) > 3 and len(line) < 30 and line.upper() == line and not any(char.isdigit() for char in line):
                vendor_candidates.append(line)
        if vendor_candidates:
            parsed_data["vendor"] = sorted(vendor_candidates, key=len, reverse=True)[0]

    date_pattern = r'(\d{2,4}[-/\s]\d{1,2}[-/\s]\d{1,2})'
    date_match = re.search(date_pattern, text)
    if date_match:
        parsed_data["date"] = date_match.group(1).strip()
    
    # --- Stage 2: "Numbers First" Mathematical Parsing ---
    all_amounts = sorted(list(set([float(m.replace(',', '.')) for m in re.findall(r'(\d+[.,]\d{2})', text)])), reverse=True)
    
    if len(all_amounts) >= 2:
        # Assumption 1: Grand Total is the largest number on the receipt.
        grand_total = all_amounts[0]
        parsed_data["total_amount"] = grand_total
        
        # Assumption 2: Subtotal is the second largest number.
        subtotal = all_amounts[1]
        
        # Assumption 3: The sum of taxes can be deduced.
        expected_tax_sum = round(grand_total - subtotal, 2)
        
        # Find all other smaller numbers that could be tax components.
        tax_candidates = [amt for amt in all_amounts if amt < subtotal]
        
        validated_taxes = []
        if expected_tax_sum > 0:
            # Find a combination of candidates that perfectly adds up to the expected tax sum.
            for i in range(1, 4): # Check for 1, 2, or 3 taxes
                for combo in combinations(tax_candidates, i):
                    if abs(sum(combo) - expected_tax_sum) < 0.02: # 2 cent tolerance for rounding
                        validated_taxes = sorted(list(combo))
                        break
                if validated_taxes:
                    break
        
        # --- Stage 3: Assign validated taxes ---
        if validated_taxes:
            # If a single tax matches the sum, it could be HST.
            if len(validated_taxes) == 1:
                if any(keyword in text.lower() for keyword in ["hst", "tvh"]):
                     parsed_data["hst_amount"] = validated_taxes[0]
                else: # Otherwise, assume it's a lone GST/PST.
                     parsed_data["gst_amount"] = validated_taxes[0]
            # If two taxes are found, assume smaller is GST, larger is PST.
            elif len(validated_taxes) >= 2:
                parsed_data["gst_amount"] = validated_taxes[0]
                parsed_data["pst_amount"] = validated_taxes[1]

    # --- Stage 4: Line Item Extraction ---
    # Heuristic: A line item is a line with a number that is NOT a found total or tax.
    found_financials = [parsed_data['total_amount'], subtotal, *validated_taxes]
    
    for line in lines:
        line_amounts = [float(m.replace(',', '.')) for m in re.findall(r'(\d+[.,]\d{2})', line)]
        if len(line_amounts) == 1:
            price = line_amounts[0]
            # Check if this price is one of our main financial numbers
            is_financial = False
            for fin_val in found_financials:
                if abs(price - fin_val) < 0.02:
                    is_financial = True
                    break
            
            if not is_financial:
                description = line.replace(str(price), '').replace('$', '').strip()
                if len(description) > 3:
                    parsed_data["line_items"].append({"description": description, "price": price})

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
