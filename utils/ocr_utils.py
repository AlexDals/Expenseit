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


# --- COMPLETELY REWRITTEN PARSING LOGIC v5 (Corrected Anchor Finding) ---
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
        if parsed_data["vendor"] == "N/A": parsed_data["vendor"] = lines[0]

    date_pattern = r'(?i)(?:Date|Invoice Date)[:\s]*(\d{1,2}[-/.\s]+\w+[-/.\s]+\d{2,4}|\w+[-/.\s]+\d{1,2}[,.\s]+\d{2,4}|\d{4}[-/]\d{2}[-/]\d{2}|\d{2}[-/]\d{2}[-/]\d{4})'
    date_match = re.search(date_pattern, text)
    if date_match: parsed_data["date"] = date_match.group(1).strip()

    # --- Stage 2: More Careful Anchor Identification (Total and Subtotal) ---
    total_keywords = ["total payable", "total à payer", "invoice total"]
    subtotal_keywords = ["subtotal", "total partiel", "sous-total de l'article"]

    grand_total, subtotal = 0.0, 0.0
    all_numbers = [float(m.group(1).replace(',', '.')) for m in re.finditer(r'[$€£]?\s*(\d+[.,]\d{2})', text)]

    def find_amount_on_line_with_keywords(text_lines, keywords):
        for line in text_lines:
            if any(keyword in line.lower() for keyword in keywords):
                amounts_on_line = [float(m.group(1).replace(',', '.')) for m in re.finditer(r'[$€£]?\s*(\d+[.,]\d{2})', line)]
                if amounts_on_line:
                    return max(amounts_on_line)
        return 0.0

    grand_total = find_amount_on_line_with_keywords(lines, total_keywords)
    subtotal = find_amount_on_line_with_keywords(lines, subtotal_keywords)

    # Fallback logic if keywords are not found or on different lines
    if grand_total == 0.0 and all_numbers: grand_total = max(all_numbers)
    # For the Amazon receipt, subtotal is often "(excl. tax)"
    if subtotal == 0.0:
        for line in lines:
            if "(excl. tax)" in line.lower():
                 amounts = [float(m.group(1).replace(',', '.')) for m in re.finditer(r'[$€£]?\s*(\d+[.,]\d{2})', line)]
                 if amounts:
                     subtotal = amounts[0]
                     break

    parsed_data["total_amount"] = grand_total

    # --- Stage 3: Mathematical Validation to find tax amounts ---
    tax_candidates = sorted([n for n in all_numbers if n not in [grand_total, subtotal] and n > 0], reverse=True)
    validated_taxes = []

    if subtotal > 0 and grand_total > subtotal and tax_candidates:
        for i in range(1, len(tax_candidates) + 1):
            for combo in combinations(tax_candidates, i):
                if abs((subtotal + sum(combo)) - grand_total) < 0.02:
                    validated_taxes = sorted(list(combo))
                    break
            if validated_taxes:
                break
    
    # --- Stage 4: Label the validated taxes using context ---
    if validated_taxes:
        gst_keywords = ["gst", "tps", "federal tax"]
        pst_keywords = ["pst", "qst", "tvp", "provincial tax"]
        hst_keywords = ["hst", "tvh"]

        # This heuristic assumes on Canadian receipts that GST is usually listed before/is smaller than PST
        # This is not always true but is a reasonable default for unlabeled numbers
        if len(validated_taxes) == 1:
            # If only one tax, it could be GST or HST. We check for HST keywords first.
            if any(keyword in text.lower() for keyword in hst_keywords):
                parsed_data["hst_amount"] = validated_taxes[0]
            else:
                parsed_data["gst_amount"] = validated_taxes[0]
        elif len(validated_taxes) == 2:
            parsed_data["gst_amount"] = validated_taxes[0] # Smaller tax
            parsed_data["pst_amount"] = validated_taxes[1] # Larger tax
    
    return parsed_data
