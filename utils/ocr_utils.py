import pytesseract
from PIL import Image
import io
import re
import fitz  # PyMuPDF
import cv2  # OpenCV
import numpy as np

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


# --- COMPLETELY REWRITTEN PARSING LOGIC v3 ---
def parse_ocr_text(text: str):
    """
    Parses OCR text using a more precise context-aware method with negative keywords
    to correctly identify totals and taxes.
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
        # A simple heuristic for vendor name, might need improvement
        if "sold by" not in lines[0].lower() and len(lines[0]) < 50:
             parsed_data["vendor"] = lines[0]
        else:
             # Look for "Sold by" line as a better indicator
             for line in lines:
                 if line.lower().startswith("sold by / vendu par:"):
                     parsed_data["vendor"] = line.split(":")[1].strip()
                     break

    date_pattern = r'(?i)(?:Date|date de la facture|Invoice Date)[:\s]*(\d{1,2}[-/.\s]+\w+[-/.\s]+\d{2,4}|\w+[-/.\s]+\d{1,2}[,.\s]+\d{2,4}|\d{4}[-/]\d{2}[-/]\d{2}|\d{2}[-/]\d{2}[-/]\d{4})'
    date_match = re.search(date_pattern, text)
    if date_match:
        parsed_data["date"] = date_match.group(1).strip()

    # --- New, More Precise Tax and Total Parsing ---
    
    # Define keywords for different categories, including negative keywords
    total_keywords = ["total payable", "total à payer", "invoice total"]
    gst_keywords = ["gst", "tps", "federal tax", "taxe fédérale"]
    pst_keywords = ["pst", "qst", "tvp", "provincial tax", "taxe provinciale"]
    hst_keywords = ["hst", "tvh"]
    
    # Keywords to ignore when looking for a specific tax, to avoid mis-categorization
    tax_negative_keywords = ["total", "subtotal", "shipping", "expédition", "balance", "solde"]

    money_pattern = r'[$€£]?\s*(\d+[.,]\d{2})'
    
    # Pass 1: Find the most likely candidates for each category
    total_candidates = []
    gst_candidates = []
    pst_candidates = []
    hst_candidates = []
    
    for line in text.split('\n'):
        line_lower = line.lower()
        
        # Find all amounts in the current line
        amounts_in_line = [float(m.replace(',', '')) for m in re.findall(r'(\d+[.,]\d{2})', line)]
        if not amounts_in_line:
            continue
        
        # Check for Total: Highest priority
        if any(keyword in line_lower for keyword in total_keywords):
            total_candidates.extend(amounts_in_line)
            continue # If it's a total line, don't check for taxes on it

        # Check for Taxes, but only if it's NOT a line with negative keywords
        if not any(neg_keyword in line_lower for neg_keyword in tax_negative_keywords):
            if any(keyword in line_lower for keyword in gst_keywords):
                gst_candidates.extend(amounts_in_line)
            if any(keyword in line_lower for keyword in pst_keywords):
                pst_candidates.extend(amounts_in_line)
            if any(keyword in line_lower for keyword in hst_keywords):
                hst_candidates.extend(amounts_in_line)

    # Pass 2: Assign the best candidate to the final result
    if total_candidates:
        parsed_data["total_amount"] = max(total_candidates)
    else:
        # Fallback: if no specific total found, find largest amount overall
        all_amounts = [float(m.replace(',', '')) for m in re.findall(r'(\d+[.,]\d{2})', text)]
        if all_amounts:
            parsed_data["total_amount"] = max(all_amounts)

    if gst_candidates:
        parsed_data["gst_amount"] = gst_candidates[0] # Assume first found is correct
    if pst_candidates:
        parsed_data["pst_amount"] = pst_candidates[0] # Assume first found is correct
    if hst_candidates:
        parsed_data["hst_amount"] = hst_candidates[0] # Assume first found is correct
        
    # Final check: In your specific document, the tax values are explicitly listed in a table row.
    # We can add a very specific regex for that table structure as a final override.
    tax_table_pattern = re.search(r"(\d+[.,]\d{2})\s+Total\s+(\d+[.,]\d{2})\s+(\d+[.,]\d{2})\s+(\d+[.,]\d{2})", text.replace('$', ''))
    if tax_table_pattern:
        # This pattern matches: subtotal, gst, pst, tax_total
        gst_val_from_table = float(tax_table_pattern.group(2))
        pst_val_from_table = float(tax_table_pattern.group(3))
        # Only assign if they are greater than 0, to not overwrite correct values with 0
        if gst_val_from_table > 0:
            parsed_data["gst_amount"] = gst_val_from_table
        if pst_val_from_table > 0:
            parsed_data["pst_amount"] = pst_val_from_table

    return parsed_data
