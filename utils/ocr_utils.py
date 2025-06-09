import pytesseract
from PIL import Image
import io
import re

def extract_text_from_image(image_bytes):
    try:
        image = Image.open(io.BytesIO(image_bytes))
        text = pytesseract.image_to_string(image)
        return text
    except Exception as e:
        return f"Error during OCR: {str(e)}"

def parse_ocr_text(text):
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
