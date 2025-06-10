import pytesseract
from PIL import Image
import io
import re
import fitz  # PyMuPDF
import cv2  # OpenCV
import numpy as np

# --- IMAGE PREPROCESSING (No changes) ---
def preprocess_image_for_ocr(image_bytes):
    try:
        img_array = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        edged = cv2.Canny(blur, 75, 200)
        contours, _ = cv2.findContours(edged.copy(), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        contours = sorted(contours, key=cv2.contourArea, reverse=True)[:5]
        screen_contour = None
        for c in contours:
            peri = cv2.arcLength(c, True)
            approx = cv2.approxPolyDP(c, 0.02 * peri, True)
            if len(approx) == 4:
                screen_contour = approx
                break
        
        if screen_contour is not None:
            pts = screen_contour.reshape(4, 2)
            rect = np.zeros((4, 2), dtype="float32")
            s = pts.sum(axis=1)
            rect[0] = pts[np.argmin(s)]
            rect[2] = pts[np.argmax(s)]
            diff = np.diff(pts, axis=1)
            rect[1] = pts[np.argmin(diff)]
            rect[3] = pts[np.argmax(diff)]
            (tl, tr, br, bl) = rect
            widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
            widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
            maxWidth = max(int(widthA), int(widthB))
            heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
            heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
            maxHeight = max(int(heightA), int(heightB))
            dst = np.array([[0, 0], [maxWidth - 1, 0], [maxWidth - 1, maxHeight - 1], [0, maxHeight - 1]], dtype="float32")
            M = cv2.getPerspectiveTransform(rect, dst)
            warped = cv2.warpPerspective(img, M, (maxWidth, maxHeight))
            output_img = cv2.cvtColor(warped, cv2.COLOR_BGR_GRAY)
        else:
            output_img = gray
            
        _, final_img = cv2.threshold(output_img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        _, processed_img_bytes = cv2.imencode('.png', final_img)
        return processed_img_bytes.tobytes()
    except Exception:
        img_array = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
        _, processed_img_bytes = cv2.imencode('.png', thresh)
        return processed_img_bytes.tobytes()

# --- TEXT EXTRACTION (No changes) ---
def extract_text_from_file(uploaded_file):
    try:
        file_bytes = uploaded_file.getvalue()
        full_text = ""
        custom_config = r'--oem 3 --psm 6'
        if uploaded_file.type == "application/pdf":
            with fitz.open(stream=file_bytes, filetype="pdf") as doc:
                for page_num, page in enumerate(doc):
                    pix = page.get_pixmap(dpi=300)
                    img_bytes = pix.tobytes("png")
                    processed_bytes = preprocess_image_for_ocr(img_bytes)
                    image = Image.open(io.BytesIO(processed_bytes))
                    page_text = pytesseract.image_to_string(image, config=custom_config)
                    full_text += page_text + f"\n--- Page {page_num+1} ---\n"
            return full_text
        elif uploaded_file.type in ["image/png", "image/jpeg", "image/jpg"]:
            processed_bytes = preprocess_image_for_ocr(file_bytes)
            image = Image.open(io.BytesIO(processed_bytes))
            return pytesseract.image_to_string(image, config=custom_config)
        else:
            return "Unsupported file type."
    except Exception as e:
        return f"Error during OCR processing: {str(e)}"

# --- NEW PARSING LOGIC: TARGETED REGEX ---
def parse_ocr_text(text: str):
    parsed_data = {
        "vendor": "N/A", "date": "N/A", "total_amount": 0.0,
        "gst_amount": 0.0, "pst_amount": 0.0, "hst_amount": 0.0,
        "line_items": []
    }
    
    lines = [line.strip() for line in text.split('\n') if line.strip()]

    # --- Vendor and Date Extraction ---
    # Vendor is often the first significant capitalized line
    for line in lines:
        if len(line) > 3 and line.isupper():
            parsed_data["vendor"] = line
            break

    date_pattern = r'(?i)(?:Date|facturation)[:\s]*(\d{1,2}\s+\w+\s+\d{4})' # For "27 May 2025"
    date_match = re.search(date_pattern, text)
    if date_match:
        parsed_data["date"] = date_match.group(1).strip()
    else: # Fallback for other formats like yy mm/dd
        date_pattern_alt = r'(\d{2})\s(\d{2}/\d{2})'
        date_match_alt = re.search(date_pattern_alt, text)
        if date_match_alt:
            parsed_data["date"] = f"20{date_match_alt.group(1)}-{date_match_alt.group(2).replace('/', '-')}"
    
    # --- Targeted Regex for Totals and Taxes ---
    def find_value_by_keyword(text, keywords):
        for keyword in keywords:
            # Pattern: keyword, optional colon, optional space, optional $, the number
            pattern = re.compile(fr'(?i){keyword}\s*:?\s*[$]?\s*(\d+[.,]\d{{2}})')
            match = pattern.search(text)
            if match:
                return float(match.group(1).replace(',', '.'))
        return 0.0

    parsed_data["total_amount"] = find_value_by_keyword(text, ["Total", "Total payable"])
    parsed_data["gst_amount"] = find_value_by_keyword(text, ["TPS", "GST"])
    parsed_data["pst_amount"] = find_value_by_keyword(text, ["TVQ", "QST", "PST"])
    parsed_data["hst_amount"] = find_value_by_keyword(text, ["HST", "TVH"])

    # --- Line Item Extraction ---
    # This is a heuristic: assumes a line item has text at the start and a price at the end
    line_item_pattern = re.compile(r'^(.*?)\s+([$]?\d+[.,]\d{2})$', re.MULTILINE)
    subtotal_keywords = ["sous-total", "subtotal", "total partiel"]
    
    for line in lines:
        match = line_item_pattern.match(line)
        # Check if it's a line item and not a total/tax line
        if match and not any(keyword in line.lower() for keyword in subtotal_keywords + ["tps", "tvq", "total"]):
            description = match.group(1).strip()
            # Ignore lines that are likely not items
            if len(description) < 4 or description.isupper():
                continue
            
            price = float(match.group(2).replace('$', '').replace(',', '.'))
            parsed_data["line_items"].append({"description": description, "price": price})

    return parsed_data

# --- Main Entry Point Function (No changes) ---
def extract_and_parse_file(uploaded_file):
    try:
        raw_text = extract_text_from_file(uploaded_file)
        if "Error" in raw_text or "Unsupported" in raw_text:
             return raw_text, {"error": raw_text}
        parsed_data = parse_ocr_text(raw_text)
        return raw_text, parsed_data
    except Exception as e:
        error_message = f"A critical error occurred in the OCR pipeline: {str(e)}"
        return error_message, {"error": error_message}
