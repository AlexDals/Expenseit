import pytesseract
from PIL import Image
import io
import re
import fitz  # PyMuPDF
import cv2  # OpenCV
import numpy as np
from itertools import combinations

# --- IMAGE PREPROCESSING FUNCTION (No changes) ---
def preprocess_image(image_bytes):
    img_array = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                   cv2.THRESH_BINARY, 11, 2)
    _, processed_img_bytes = cv2.imencode('.png', thresh)
    return processed_img_bytes.tobytes()


# --- UPGRADED TEXT EXTRACTION (No changes) ---
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
            return "Unsupported file type. Please upload an image or PDF."
            
    except Exception as e:
        return f"Error during OCR processing: {str(e)}"


# --- COMPLETELY REWRITTEN PARSING LOGIC v4 (Mathematical Approach) ---
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
                parsed_data["vendor"] = line.split(":")[1].strip()
                break
        if parsed_data["vendor"] == "N/A": parsed_data["vendor"] = lines[0]

    date_pattern = r'(?i)(?:Date|date de la facture|Invoice Date)[:\s]*(\d{1,2}[-/.\s]+\w+[-/.\s]+\d{2,4}|\w+[-/.\s]+\d{1,2}[,.\s]+\d{2,4}|\d{4}[-/]\d{2}[-/]\d{2}|\d{2}[-/]\d{2}[-/]\d{4})'
    date_match = re.search(date_pattern, text)
    if date_match: parsed_data["date"] = date_match.group(1).strip()

    # --- Stage 2: Extract all numbers and identify key anchors (Total and Subtotal) ---
    total_keywords = ["total payable", "total à payer", "invoice total"]
    subtotal_keywords = ["subtotal", "total partiel", "sous-total"]
    gst_keywords = ["gst", "tps", "federal tax", "taxe fédérale"]
    pst_keywords = ["pst", "qst", "tvp", "provincial tax", "taxe provinciale"]
    hst_keywords = ["hst", "tvh"]

    grand_total, subtotal = 0.0, 0.0
    all_numbers = []
    
    # Use finditer to get values and their positions
    for match in re.finditer(r'[$€£]?\s*(\d+[.,]\d{2})', text):
        amount = float(match.group(1).replace(',', '.'))
        all_numbers.append(amount)
        context_line = ""
        # Find the full line where the match occurred for context
        for line in text.split('\n'):
            if match.group(0) in line:
                context_line = line.lower()
                break
        
        if any(keyword in context_line for keyword in total_keywords):
            grand_total = max(grand_total, amount)
        elif any(keyword in context_line for keyword in subtotal_keywords):
            subtotal = max(subtotal, amount)

    # If anchors aren't found, make educated guesses
    if grand_total == 0.0 and all_numbers: grand_total = max(all_numbers)
    if subtotal == 0.0 and all_numbers:
        # Guess subtotal is the second largest number if available
        unique_sorted_amounts = sorted(list(set(all_numbers)), reverse=True)
        if len(unique_sorted_amounts) > 1:
            subtotal = unique_sorted_amounts[1]
    
    parsed_data["total_amount"] = grand_total
    
    # --- Stage 3: Mathematical Validation to find tax amounts ---
    tax_candidates = sorted([n for n in all_numbers if n not in [grand_total, subtotal] and n > 0], reverse=True)
    validated_taxes = []

    if subtotal > 0 and grand_total > subtotal:
        for i in range(1, len(tax_candidates) + 1):
            for combo in combinations(tax_candidates, i):
                # Check if subtotal + combination of taxes is close to the total
                if abs((subtotal + sum(combo)) - grand_total) < 0.02:
                    validated_taxes = list(combo)
                    break
            if validated_taxes:
                break
    
    # --- Stage 4: Label the validated taxes using context ---
    if validated_taxes:
        unassigned_taxes = list(validated_taxes)
        for tax_val in validated_taxes:
            # Find the original line for this tax value to check its context
            for line in text.split('\n'):
                if str(f"{tax_val:.2f}").replace('.', r'\.') in line.replace(',', '.'):
                    line_lower = line.lower()
                    # Check for HST first (exclusive)
                    if any(keyword in line_lower for keyword in hst_keywords):
                        parsed_data["hst_amount"] = tax_val
                        if tax_val in unassigned_taxes: unassigned_taxes.remove(tax_val)
                        break
                    # Check for GST
                    if any(keyword in line_lower for keyword in gst_keywords):
                        parsed_data["gst_amount"] = tax_val
                        if tax_val in unassigned_taxes: unassigned_taxes.remove(tax_val)
                        break
                    # Check for PST
                    if any(keyword in line_lower for keyword in pst_keywords):
                        parsed_data["pst_amount"] = tax_val
                        if tax_val in unassigned_taxes: unassigned_taxes.remove(tax_val)
                        break
        # Heuristic for documents where taxes are listed without keywords on the same line
        # It assumes the smaller tax is GST and the larger is PST if they are unlabeled
        if len(unassigned_taxes) == 2 and parsed_data["hst_amount"] == 0.0:
            unassigned_taxes.sort()
            parsed_data["gst_amount"] = unassigned_taxes[0]
            parsed_data["pst_amount"] = unassigned_taxes[1]
    
    return parsed_data
