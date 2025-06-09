import pytesseract
from PIL import Image
import io
import re
import fitz  # PyMuPDF
import cv2  # OpenCV
import numpy as np

# --- IMAGE PREPROCESSING FUNCTION (No changes) ---
def preprocess_image(image_bytes):
    """
    Cleans up an image for better OCR results.
    - Converts to grayscale
    - Applies a binary threshold
    """
    img_array = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                   cv2.THRESH_BINARY, 11, 2)
    _, processed_img_bytes = cv2.imencode('.png', thresh)
    return processed_img_bytes.tobytes()


# --- UPGRADED TEXT EXTRACTION (No changes) ---
def extract_text_from_file(uploaded_file):
    """
    Extracts text from an uploaded file, supporting both images and PDFs.
    Includes high-resolution rendering and image preprocessing.
    """
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


# --- COMPLETELY REWRITTEN PARSING LOGIC ---
def parse_ocr_text(text: str):
    """
    Parses OCR text by finding all monetary values and analyzing their context
    to identify totals, taxes, and other key fields.
    """
    # Initialize data structure
    parsed_data = {
        "vendor": "N/A",
        "date": "N/A",
        "total_amount": 0.0,
        "gst_amount": 0.0,
        "pst_amount": 0.0,
        "hst_amount": 0.0,
    }

    # --- Vendor and Date Parsing (No changes) ---
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    if lines:
        parsed_data["vendor"] = lines[0]

    date_pattern = r'(?i)(?:Date|date de la facture|Invoice Date)[:\s]*(\d{1,2}[-/.\s]+\w+[-/.\s]+\d{2,4}|\w+[-/.\s]+\d{1,2}[,.\s]+\d{2,4}|\d{4}[-/]\d{2}[-/]\d{2}|\d{2}[-/]\d{2}[-/]\d{4})'
    date_match = re.search(date_pattern, text)
    if date_match:
        parsed_data["date"] = date_match.group(1).strip()

    # --- New Context-Aware Tax and Total Parsing ---
    
    # Define keywords for different categories
    total_keywords = ["total payable", "total à payer", "invoice total", "total de la facture"]
    gst_keywords = ["gst", "tps", "federal tax", "taxe fédérale"]
    pst_keywords = ["pst", "qst", "tvp", "provincial tax", "taxe provinciale"]
    hst_keywords = ["hst", "tvh"]
    ignore_keywords = ["subtotal", "partiel", "balance", "solde"]

    # Find all monetary values in the text
    money_pattern = r'([$€£]?\s*\d+[.,]\d{2})'
    
    # Use finditer to get match objects with positions
    for match in re.finditer(money_pattern, text):
        try:
            amount_str = match.group(1).replace('$', '').replace('€', '').replace('£', '').replace(',', '').strip()
            amount_val = float(amount_str)

            # Define a "context window" of text around the found amount
            context_start = max(0, match.start() - 75)
            context_end = min(len(text), match.end() + 75)
            context = text[context_start:context_end].lower()

            # Check for keywords in the context, starting with the most specific (Total)
            is_total = any(keyword in context for keyword in total_keywords)
            is_ignored = any(keyword in context for keyword in ignore_keywords)
            
            if is_total and not is_ignored:
                # If we find a specific total keyword, we are confident this is the one.
                # We can even overwrite if we find a better one.
                parsed_data["total_amount"] = max(parsed_data["total_amount"], amount_val)
                continue # Skip checking for taxes if it's a total

            # Check for tax keywords if it wasn't a total
            if any(keyword in context for keyword in gst_keywords):
                parsed_data["gst_amount"] = amount_val
            elif any(keyword in context for keyword in pst_keywords):
                parsed_data["pst_amount"] = amount_val
            elif any(keyword in context for keyword in hst_keywords):
                parsed_data["hst_amount"] = amount_val

        except (ValueError, IndexError):
            continue
            
    # If no specific "total payable" was found, fall back to the largest monetary value
    if parsed_data["total_amount"] == 0.0:
        all_amounts = [float(m.group(1).replace('$', '').replace(',', '')) for m in re.finditer(money_pattern, text)]
        if all_amounts:
            parsed_data["total_amount"] = max(all_amounts)

    return parsed_data
