import pytesseract
from PIL import Image
import io
import re
import fitz  # PyMuPDF
import cv2  # OpenCV
import numpy as np

def preprocess_image_for_ocr(image_bytes):
    """Advanced preprocessing with perspective correction."""
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
            rect[0] = pts[np.argmin(s)]; rect[2] = pts[np.argmax(s)]
            diff = np.diff(pts, axis=1)
            rect[1] = pts[np.argmin(diff)]; rect[3] = pts[np.argmax(diff)]
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

def extract_text_from_file(uploaded_file):
    """Extracts text from file using OCR."""
    try:
        file_bytes = uploaded_file.getvalue()
        full_text = ""
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
    """Parses OCR text using targeted, line-by-line regular expressions."""
    parsed_data = {"vendor": "N/A", "date": "N/A", "total_amount": 0.0, "gst_amount": 0.0, "pst_amount": 0.0, "hst_amount": 0.0, "line_items": []}
    lines = [line.strip() for line in text.split('\n') if line.strip()]

    # Define specific regex patterns for each field
    # Using negative lookbehind `(?i)(?<!sous-)(?<!sub)` to find "Total" but not "Sub-total"
    total_pattern = re.compile(r'(?i)(?<!sous-)(?<!sub)total[:\s]*([$]?\s*\d+[.,]\d{2})')
    subtotal_pattern = re.compile(r'(?i)(?:sous-total|subtotal)[:\s]*([$]?\s*\d+[.,]\d{2})')
    tps_pattern = re.compile(r'(?i)(?:tps|gst)[:\s]*([$]?\s*\d+[.,]\d{2})')
    tvq_pattern = re.compile(r'(?i)(?:tvq|qst)[:\s]*([$]?\s*\d+[.,]\d{2})')
    hst_pattern = re.compile(r'(?i)(?:hst|tvh)[:\s]*([$]?\s*\d+[.,]\d{2})')
    line_item_pattern = re.compile(r'^(.*?)\s+([$]?\d+[.,]\d{2})$')
    
    financial_keywords = ["total", "sous-total", "subtotal", "tps", "gst", "tvq", "qst", "hst", "tvh", "ecofrais"]

    # --- Data Extraction Pass ---
    for line in lines:
        if match := total_pattern.search(line):
            parsed_data['total_amount'] = float(match.group(1).replace('$', '').replace(',', '.'))
        elif match := tps_pattern.search(line):
            parsed_data['gst_amount'] = float(match.group(1).replace('$', '').replace(',', '.'))
        elif match := tvq_pattern.search(line):
            parsed_data['pst_amount'] = float(match.group(1).replace('$', '.'))
        elif match := hst_pattern.search(line):
            parsed_data['hst_amount'] = float(match.group(1).replace('$', '').replace(',', '.'))
        elif match := line_item_pattern.match(line):
            description = match.group(1).strip()
            # Check if the line is likely a line item and not something else
            if len(description) > 2 and not any(keyword in description.lower() for keyword in financial_keywords):
                price = float(match.group(2).replace('$', '').replace(',', '.'))
                # Avoid capturing the subtotal as a line item
                if not any(sub_kw in description.lower() for sub_kw in subtotal_keywords):
                    parsed_data["line_items"].append({"description": description, "price": price})

    # --- Vendor and Date Extraction ---
    if lines:
        vendor_candidates = []
        for line in lines[:5]: # Check top 5 lines for vendor
            if len(line) > 3 and line.isupper() and not any(kw in line.lower() for kw in ["invoice", "facture", "date", "caissier"]):
                vendor_candidates.append(line)
        if vendor_candidates:
            parsed_data["vendor"] = sorted(vendor_candidates, key=len, reverse=True)[0]

    date_pattern = r'(?i)(?:Date|facturation|DATE HEURE)[:\s]*((?:\d{1,2}\s+\w+\s+\d{4})|(?:\d{2,4}[-/\s]\d{1,2}[-/\s]\d{1,2}))'
    date_match = re.search(date_pattern, text)
    if date_match:
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
