import pytesseract
from PIL import Image
import io
import re
import fitz  # PyMuPDF

def extract_text_from_file(uploaded_file):
    """
    Extracts text from an uploaded file, supporting both images and PDFs.
    """
    try:
        file_bytes = uploaded_file.getvalue()
        
        # Check if the file is a PDF
        if uploaded_file.type == "application/pdf":
            full_text = ""
            with fitz.open(stream=file_bytes, filetype="pdf") as doc:
                for page in doc:
                    # Convert PDF page to an image (pixmap)
                    pix = page.get_pixmap()
                    img_bytes = pix.tobytes("png")
                    image = Image.open(io.BytesIO(img_bytes))
                    # Perform OCR on the image of the page
                    page_text = pytesseract.image_to_string(image)
                    full_text += page_text + "\n\n" # Add separator for each page
            return full_text
        
        # Handle image files
        elif uploaded_file.type in ["image/png", "image/jpeg", "image/jpg"]:
            image = Image.open(io.BytesIO(file_bytes))
            return pytesseract.image_to_string(image)
        
        else:
            return "Unsupported file type. Please upload an image or PDF."
            
    except Exception as e:
        return f"Error during OCR processing: {str(e)}"

def parse_ocr_text(text):
    """
    This function remains the same. It parses the final text string,
    regardless of whether it came from an image or a PDF.
    """
    parsed_data = {
        "vendor": "N/A",
        "date": "N/A",
        "total_amount": 0.0,
    }
    amount_match = re.search(r'(?:TOTAL|AMOUNT|Total|Amount)[:\s\$€£]*([\d,]+\.\d{2})', text, re.IGNORECASE)
    if amount_match:
        try:
            parsed_data["total_amount"] = float(amount_match.group(1).replace(',', ''))
        except ValueError:
            pass
    date_match = re.search(r'(\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}\s(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s\d{2,4})', text)
    if date_match:
        parsed_data["date"] = date_match.group(0)
    lines = text.split('\n')
    if lines and len(lines[0].strip()) > 3 and len(lines[0].strip()) < 50 :
        parsed_data["vendor"] = lines[0].strip()
    return parsed_data
