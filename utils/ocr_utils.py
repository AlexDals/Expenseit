import pytesseract
from PIL import Image
import io
import re
import fitz  # PyMuPDF
import cv2  # OpenCV
import numpy as np
from itertools import combinations

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
    parsed_data = {"vendor": "N/A", "date": "N/A", "total_amount": 0.0, "gst_amount": 0.0, "pst_amount": 0.0, "hst_amount": 0.0, "line_items": []}
    lines = [line.strip() for line in text.split('\n') if line.strip()]

    # --- Keyword Definitions ---
    total_keywords = ["total", "total payable", "total à payer"]
    subtotal_keywords = ["sous-total", "subtotal", "total partiel"]
    gst_keywords = ["tps", "gst"]
    pst_keywords = ["tvq", "qst", "tvp", "pst"]
    hst_keywords = ["hst", "tvh"]
    all_financial_keywords = total_keywords + subtotal_keywords + gst_keywords + pst_keywords + hst_keywords

    # --- Line Item and Financial Data Extraction ---
    line_item_pattern = re.compile(r'^(.*?)\s+([$]?\d+[.,]\d{2})$')
    
    for line in lines:
        line_lower = line.lower()
        
        # --- Targeted Value Extraction ---
        def get_value_from_line(keywords):
            if any(keyword in line_lower for keyword in keywords):
                amounts = re.findall(r'(\d+[.,]\d{2})', line)
                if amounts:
                    return float(amounts[-1].replace(',', '.'))
            return None

        # Extract values if keywords are present
        if (total_val := get_value_from_line(total_keywords)) is not None:
            parsed_data["total_amount"] = total_val
        if (gst_val := get_value_from_line(gst_keywords)) is not None:
            parsed_data["gst_amount"] = gst_val
        if (pst_val := get_value_from_line(pst_keywords)) is not None:
            parsed_data["pst_amount"] = pst_val
        if (hst_val := get_value_from_line(hst_keywords)) is not None:
            parsed_data["hst_amount"] = hst_val
            
        # --- Line Item Extraction ---
        match = line_item_pattern.match(line)
        if match and not any(keyword in line_lower for keyword in all_financial_keywords):
            description = match.group(1).strip()
            price = float(match.group(2).replace('$', '').replace(',', '.'))
            if len(description) > 2 and not description.isupper():
                parsed_data["line_items"].append({"description": description, "price": price})

    # --- Vendor and Date Extraction ---
    if lines:
        # Heuristic: First significant capitalized line is often the vendor
        for line in lines:
            if len(line) > 3 and line.isupper() and not any(kw in line.lower() for kw in ["invoice", "facture", "date"]):
                parsed_data["vendor"] = line
                break
    
    date_pattern = r'(\d{2,4}[-/\s]\d{1,2}[-/\s]\d{1,2})' # General date pattern
    date_match = re.search(date_pattern, text)
    if date_match:
        parsed_data["date"] = date_match.group(1).strip()

    return parsed_data

def extract_and_parse_file(uploaded_file):
    try:
        raw_text = extract_text_from_file(uploaded_file)
        if "Error" in raw_text or "Unsupported" in raw_text:
            return raw_text, {"error": raw_text}
        parsed_data = parse_ocr_text(raw_text)
        return raw_text, parsed_data
    except Exception as e:
        error_message = f"A critical error occurred: {str(e)}"
        return error_message, {"error": error_message}
