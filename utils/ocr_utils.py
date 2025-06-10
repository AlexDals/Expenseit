import pytesseract
from PIL import Image
import io
import re
import fitz  # PyMuPDF
import cv2  # OpenCV
import numpy as np
from itertools import combinations

# --- NEW ADVANCED IMAGE PREPROCESSING ---
def preprocess_image_for_ocr(image_bytes):
    """
    Applies a series of advanced preprocessing steps to an image to
    prepare it for OCR, including perspective correction.
    """
    try:
        # Decode image
        img_array = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

        # 1. Grayscale and Blur
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)

        # 2. Edge Detection
        edged = cv2.Canny(blur, 75, 200)

        # 3. Find Contours and the Largest One (assumed to be the receipt)
        contours, _ = cv2.findContours(edged.copy(), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        contours = sorted(contours, key=cv2.contourArea, reverse=True)[:5]

        screen_contour = None
        for c in contours:
            peri = cv2.arcLength(c, True)
            approx = cv2.approxPolyDP(c, 0.02 * peri, True)
            if len(approx) == 4:
                screen_contour = approx
                break
        
        # 4. Perspective Transform (if a 4-point contour is found)
        if screen_contour is not None:
            # Order the points
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
            
            dst = np.array([
                [0, 0],
                [maxWidth - 1, 0],
                [maxWidth - 1, maxHeight - 1],
                [0, maxHeight - 1]], dtype="float32")

            # Apply the perspective warp
            M = cv2.getPerspectiveTransform(rect, dst)
            warped = cv2.warpPerspective(img, M, (maxWidth, maxHeight))
            
            # Use the warped image for further processing
            output_img = cv2.cvtColor(warped, cv2.COLOR_BGR_GRAY)
        else:
            # If no contour found, fall back to the original grayscale image
            output_img = gray
            
        # 5. Final Thresholding for clean text
        _, final_img = cv2.threshold(output_img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        _, processed_img_bytes = cv2.imencode('.png', final_img)
        return processed_img_bytes.tobytes()

    except Exception:
        # If any advanced step fails, fall back to the simple process
        return preprocess_image_simple(image_bytes)

def preprocess_image_simple(image_bytes):
    """A fallback simple preprocessing function."""
    img_array = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                   cv2.THRESH_BINARY, 11, 2)
    _, processed_img_bytes = cv2.imencode('.png', thresh)
    return processed_img_bytes.tobytes()


# --- TEXT EXTRACTION (Updated to use new preprocessing) ---
def extract_text_from_file(uploaded_file):
    try:
        file_bytes = uploaded_file.getvalue()
        full_text = ""
        # Use PSM 6 for receipts, it's often better at single-column layouts
        custom_config = r'--oem 3 --psm 6'

        if uploaded_file.type == "application/pdf":
            with fitz.open(stream=file_bytes, filetype="pdf") as doc:
                for page_num, page in enumerate(doc):
                    pix = page.get_pixmap(dpi=300)
                    img_bytes = pix.tobytes("png")
                    # Use the advanced preprocessor
                    processed_bytes = preprocess_image_for_ocr(img_bytes)
                    image = Image.open(io.BytesIO(processed_bytes))
                    page_text = pytesseract.image_to_string(image, config=custom_config)
                    full_text += page_text + f"\n--- Page {page_num+1} ---\n"
            return full_text
        elif uploaded_file.type in ["image/png", "image/jpeg", "image/jpg"]:
            # Use the advanced preprocessor
            processed_bytes = preprocess_image_for_ocr(file_bytes)
            image = Image.open(io.BytesIO(processed_bytes))
            return pytesseract.image_to_string(image, config=custom_config)
        else:
            return "Unsupported file type."
    except Exception as e:
        return f"Error during OCR processing: {str(e)}"

# --- MATHEMATICAL PARSING LOGIC (No changes needed) ---
def _find_amount_from_lines(lines, keywords):
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

    date_pattern = r'(?i)(?:Date|Invoice Date|DATE HEURE)[:\s]*(\d{2,4}[/.\s]+\d{1,2}[/.\s]+\d{1,2})'
    date_match = re.search(date_pattern, text)
    if date_match: parsed_data["date"] = date_match.group(1).strip()

    all_amounts = sorted(list(set([float(m.replace(',', '.')) for m in re.findall(r'(\d+[.,]\d{2})', text)])), reverse=True)
    
    if len(all_amounts) >= 2:
        grand_total = all_amounts[0]
        subtotal = 0
        # Find subtotal by looking for the second largest number that is reasonably smaller
        for amount in all_amounts[1:]:
            if amount < grand_total * 0.98: # Subtotal should not be almost identical to total
                subtotal = amount
                break
        
        if subtotal == 0 and len(all_amounts) > 1: subtotal = all_amounts[1]
        
        parsed_data["total_amount"] = grand_total
        
        expected_tax_sum = round(grand_total - subtotal, 2)
        tax_candidates = [amt for amt in all_amounts if amt < subtotal and abs(amt - expected_tax_sum) > 0.01]
        
        validated_taxes = []
        if expected_tax_sum > 0:
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

# --- Main Entry Point Function (No changes needed) ---
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
