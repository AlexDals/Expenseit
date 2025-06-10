import streamlit as st
from google.cloud import vision
import re
from itertools import combinations

# --- GOOGLE VISION API SETUP ---
@st.cache_resource
def get_vision_client():
    """Initializes and returns a Google Vision API client using credentials from st.secrets."""
    try:
        credentials_dict = dict(st.secrets.google_credentials)
        client = vision.ImageAnnotatorClient.from_service_account_info(credentials_dict)
        return client
    except Exception as e:
        st.error(f"Could not initialize Google Vision API client: {e}. Please check your Streamlit secrets.")
        st.stop()

def extract_text_from_file(uploaded_file):
    """
    Extracts text from an image or PDF file by sending it directly to Google Cloud Vision AI.
    """
    client = get_vision_client()
    file_bytes = uploaded_file.getvalue()
    
    try:
        # Google Vision can handle the raw bytes of both images and PDFs directly.
        image = vision.Image(content=file_bytes)
        
        # Use DOCUMENT_TEXT_DETECTION for dense text and better layout understanding.
        response = client.document_text_detection(image=image)
        
        if response.error.message:
            raise Exception(f"{response.error.message}")

        return response.full_text_annotation.text

    except Exception as e:
        return f"Error calling Google Vision API: {str(e)}. Please ensure the uploaded file is not corrupted."

# --- PARSING LOGIC (This remains the same powerful 'Numbers First' parser) ---
def parse_ocr_text(text: str):
    """Parses the high-quality OCR text from Google Vision."""
    parsed_data = {"vendor": "N/A", "date": "N/A", "total_amount": 0.0, "gst_amount": 0.0, "pst_amount": 0.0, "hst_amount": 0.0, "line_items": []}
    lines = [line.strip() for line in text.split('\n') if line.strip()]

    # Vendor and Date Extraction
    if lines:
        for line in lines[:5]:
            if len(line) > 3 and line.upper() == line and not any(kw in line.lower() for kw in ["invoice", "facture", "date", "caissier", "transaction"]):
                parsed_data["vendor"] = line
                break
    
    date_pattern = r'(\d{4}[-/\s]\d{1,2}[-/\s]\d{1,2})'
    date_match = re.search(date_pattern, text)
    if date_match:
        parsed_data["date"] = date_match.group(1).strip()
    
    # Mathematical Parsing for Financials
    all_amounts = sorted(list(set([float(m.replace(',', '.')) for m in re.findall(r'(\d+[.,]\d{2})', text)])), reverse=True)
    
    if len(all_amounts) >= 2:
        grand_total = all_amounts[0]
        parsed_data["total_amount"] = grand_total
        
        subtotal = 0.0
        subtotal_keywords = ["sous-total", "subtotal"]
        for line in lines:
            if any(kw in line.lower() for kw in subtotal_keywords):
                line_amounts = [float(m.replace(',', '.')) for m in re.findall(r'(\d+[.,]\d{2})', line)]
                if line_amounts:
                    subtotal = max(line_amounts)
                    break
        
        if subtotal == 0.0 and len(all_amounts) > 1:
            subtotal = all_amounts[1]
        
        expected_tax_sum = round(grand_total - subtotal, 2)
        if expected_tax_sum > 0:
            tax_candidates = [amt for amt in all_amounts if amt < subtotal and abs(amt - expected_tax_sum) > 0.01]
            validated_taxes = []
            for i in range(1, 4):
                for combo in combinations(tax_candidates, i):
                    if abs(sum(combo) - expected_tax_sum) < 0.02:
                        validated_taxes = sorted(list(combo)); break
                if validated_taxes: break
            
            if validated_taxes:
                if len(validated_taxes) == 1:
                    parsed_data["hst_amount"] = validated_taxes[0]
                elif len(validated_taxes) >= 2:
                    parsed_data["gst_amount"] = validated_taxes[0]
                    parsed_data["pst_amount"] = validated_taxes[1]

    # Line Item Extraction
    found_financials = [parsed_data['total_amount'], subtotal] + validated_taxes
    stop_keywords = ["sous-total", "subtotal", "ecofrais", "tax", "tps", "tvq", "gst", "pst", "hst", "total"]
    
    for line in lines:
        line_lower = line.lower()
        if any(keyword in line_lower for keyword in stop_keywords): continue
        
        line_amounts = [float(m.replace(',', '.')) for m in re.findall(r'(\d+[.,]\d{2})', line)]
        if len(line_amounts) == 1:
            price = line_amounts[0]
            is_financial = any(abs(price - fin_val) < 0.02 for fin_val in found_financials)
            
            if not is_financial:
                description = line.replace(str(price), '').replace('$', '').strip()
                if len(description) > 3 and "merci" not in description.lower() and "approved" not in description.lower():
                    parsed_data["line_items"].append({"description": description, "price": price})
                    
    return parsed_data

def extract_and_parse_file(uploaded_file):
    """Main pipeline function using Google Vision."""
    try:
        raw_text = extract_text_from_file(uploaded_file)
        if "Error" in raw_text:
             return raw_text, {"error": raw_text}
        
        parsed_data = parse_ocr_text(raw_text)
        return raw_text, parsed_data
        
    except Exception as e:
        error_message = f"A critical error occurred: {str(e)}"
        return error_message, {"error": error_message}
