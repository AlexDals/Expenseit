import pytesseract
from PIL import Image
import io
import re
import fitz  # PyMuPDF
import cv2  # OpenCV
import numpy as np

# --- IMAGE PREPROCESSING FUNCTION ---
def preprocess_image(image_bytes):
    """
    Cleans up an image for better OCR results.
    - Converts to grayscale
    - Applies a binary threshold
    """
    # Convert bytes to a numpy array
    img_array = np.frombuffer(image_bytes, np.uint8)
    # Decode the array into an image
    img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
    
    # Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Apply adaptive thresholding to get a clean black and white image
    thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                   cv2.THRESH_BINARY, 11, 2)
    
    # Convert the processed image back to bytes for Tesseract
    _, processed_img_bytes = cv2.imencode('.png', thresh)
    return processed_img_bytes.tobytes()


# --- UPGRADED TEXT EXTRACTION ---
def extract_text_from_file(uploaded_file):
    """
    Extracts text from an uploaded file, supporting both images and PDFs.
    Includes high-resolution rendering and image preprocessing.
    """
    try:
        file_bytes = uploaded_file.getvalue()
        full_text = ""

        # Tesseract configuration for better layout analysis
        # PSM 4: Assume a single column of text of variable sizes.
        # PSM 6: Assume a single uniform block of text.
        custom_config = r'--oem 3 --psm 4'

        if uploaded_file.type == "application/pdf":
            with fitz.open(stream=file_bytes, filetype="pdf") as doc:
                for page_num, page in enumerate(doc):
                    # Render page at high DPI for better quality
                    pix = page.get_pixmap(dpi=300)
                    img_bytes = pix.tobytes("png")
                    
                    # Preprocess the image from the PDF page
                    processed_bytes = preprocess_image(img_bytes)
                    image = Image.open(io.BytesIO(processed_bytes))

                    # Perform OCR on the cleaned-up page image
                    page_text = pytesseract.image_to_string(image, config=custom_config)
                    full_text += page_text + f"\n--- Page {page_num+1} ---\n"
            return full_text
        
        elif uploaded_file.type in ["image/png", "image/jpeg", "image/jpg"]:
            # Preprocess the uploaded image directly
            processed_bytes = preprocess_image(file_bytes)
            image = Image.open(io.BytesIO(processed_bytes))
            return pytesseract.image_to_string(image, config=custom_config)
        
        else:
            return "Unsupported file type. Please upload an image or PDF."
            
    except Exception as e:
        return f"Error during OCR processing: {str(e)}"


# --- IMPROVED REGEX PARSING ---
def parse_ocr_text(text: str):
    """
    Parses the OCR text to find key fields using more robust regular expressions.
    """
    parsed_data = {
        "vendor": "N/A",
        "date": "N/A",
        "total_amount": 0.0,
    }

    # Vendor: Try to get the first non-empty line
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    if lines:
        parsed_data["vendor"] = lines[0]

    # Date: Look for various common date formats
    date_pattern = r'(?i)(?:Date|date de la facture|Invoice Date)[:\s]*(\d{1,2}[-/.\s]+\w+[-/.\s]+\d{2,4}|\w+[-/.\s]+\d{1,2}[,.\s]+\d{2,4}|\d{4}[-/]\d{2}[-/]\d{2}|\d{2}[-/]\d{2}[-/]\d{4})'
    date_match = re.search(date_pattern, text)
    if date_match:
        parsed_data["date"] = date_match.group(1).strip()

    # Total Amount: Look for lines containing "Total", "Amount", etc., and find the largest number on that line.
    total_pattern = r'(?i)^(.*(total|amount|montant|payé)[\w\s:]*)\s*([$€£]?\s*\d+[,.]\d{2})$'
    amount_candidates = []
    for line in text.split('\n'):
        match = re.search(r'([$€£]?\s*\d+[.,]\d{2})', line)
        if match and ("total" in line.lower() or "amount" in line.lower() or "payé" in line.lower()):
            try:
                # Clean up the number string and convert to float
                amount_str = match.group(1).replace('$', '').replace('€', '').replace('£', '').replace(',', '').strip()
                amount_candidates.append(float(amount_str))
            except ValueError:
                continue
    
    if amount_candidates:
        parsed_data["total_amount"] = max(amount_candidates) # Assume the largest value is the total

    return parsed_data
