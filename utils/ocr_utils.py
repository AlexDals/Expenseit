import streamlit as st
from google.cloud import vision
import re
import fitz  # PyMuPDF for PDF handling
import io
from PIL import Image
import cv2   # OpenCV for image processing
import numpy as np
import pandas as pd
from itertools import combinations

# --- GOOGLE VISION API SETUP ---
@st.cache_resource
def get_vision_client():
    """Initializes and returns a Google Vision API client."""
    try:
        credentials_dict = dict(st.secrets.google_credentials)
        client = vision.ImageAnnotatorClient.from_service_account_info(credentials_dict)
        return client
    except Exception as e:
        st.error(f"Could not initialize Google Vision API client: {e}. Please check your Streamlit secrets.")
        st.stop()

# --- DEFINITIVE FILE EXTRACTION LOGIC ---
def extract_text_from_file(uploaded_file):
    """
    Extracts text from an image or PDF file using Google Cloud Vision AI.
    If the file is a PDF, it converts each page to an image before sending.
    """
    client = get_vision_client()
    file_bytes = uploaded_file.getvalue()
    mime_type = uploaded_file.type
    
    try:
        # If it's a PDF, process page by page
        if mime_type == "application/pdf":
            full_text = ""
            with fitz.open(stream=file_bytes, filetype="pdf") as doc:
                for page_num, page in enumerate(doc):
                    # Render page to a high-quality PNG image in memory
                    pix = page.get_pixmap(dpi=300)
                    img_bytes = pix.tobytes("png")
                    
                    image = vision.Image(content=img_bytes)
                    response = client.document_text_detection(image=image)
                    if response.error.message:
                        raise Exception(f"Google Vision API error on page {page_num+1}: {response.error.message}")
                    
                    full_text += response.full_text_annotation.text + "\n"
            return full_text
        
        # If it's an image, send it directly
        elif mime_type in ["image/png", "image/jpeg", "image/jpg"]:
            image = vision.Image(content=file_bytes)
            response = client.document_text_detection(image=image)
            if response.error.message:
                raise Exception(response.error.message)
            return response.full_text_annotation.text
        
        else:
            return "Unsupported file type. Please upload a JPG, PNG, or PDF."

    except Exception as e:
        return f"Error calling Google Vision API: {str(e)}. Please ensure the uploaded file is not corrupted."

# --- DEFINITIVE PARSING LOGIC: TWO-PASS SYSTEM ---
def parse_ocr_text(text: str):
    """Parses OCR text using a robust two-pass system."""
    parsed_data = {"vendor": "N/A", "date": "N/A", "total_amount": 0.0, "gst_amount": 0.0, "pst_amount": 0.0, "hst_amount": 0.0, "line_items": []}
    lines = [line.strip() for line in text.split('\n') if line.strip()]

    # --- Stage 1: Financial Summary Pass ---
    financial_line_indices = set()
    total_pattern = re.compile(r'(?i)(?<!sous-)(?<!sub)total[:\s]*([$]?\s*\d+[.,]\d{2})')
    gst_pattern = re.compile(r'(?i)(?:tps|gst)[\s:]*([$]?\s*\d+[.,]\d{2})')
    pst_pattern = re.compile(r'(?i)(?:tvq|qst|pst)[\s:]*([$]?\s*\d+[.,]\d{2})')
    hst_pattern = re.compile(r'(?i)(?:hst|tvh)[\s:]*([$]?\s*\d+[.,]\d{2})')
    subtotal_pattern = re.compile(r'(?i)(?:sous-total|subtotal)[\s:]*([$]?\s*\d+[.,]\d{2})')
    
    for i, line in enumerate(lines):
        if match := total_pattern.search(line):
            parsed_data['total_amount'] = float(match.group(1).replace('$', '').replace(',', '.'))
            financial_line_indices.add(i)
        elif match := gst_pattern.search(line):
            parsed_data['gst_amount'] = float(match.group(1).replace('$', '').replace(',', '.'))
            financial_line_indices.add(i)
        elif match := pst_pattern.search(line):
            parsed_data['pst_amount'] = float(match.group(1).replace('$', '.'))
            financial_line_indices.add(i)
        elif match := hst_pattern.search(line):
            parsed_data['hst_amount'] = float(match.group(1).replace('$', '').replace(',', '.'))
            financial_line_indices.add(i)
        elif match := subtotal_pattern.search(line):
            financial_line_indices.add(i)

    # --- Stage 2: Stateful Line Item Pass ---
    line_items = []
    current_description_lines = []
    price_only_pattern = re.compile(r'^[$]?(\d+[.,]\d{2})[$]?$')
    desc_and_price_pattern = re.compile(r'^(.*?)\s+[$]?(\d+[.,]\d{2})[$]?$')

    for i, line in enumerate(lines):
        if i in financial_line_indices:
            continue
        if match := price_only_pattern.match(line):
            price = float(match.group(1).replace(',', '.'))
            if current_description_lines:
                full_description = " ".join(current_description_lines)
                line_items.append({"description": full_description, "price": price})
                current_description_lines = []
        elif match := desc_and_price_pattern.match(line):
            description, price_str = match.groups()
            price = float(price_str.replace(',', '.'))
            current_description_lines.append(description)
            full_description = " ".join(current_description_lines)
            line_items.append({"description": full_description, "price": price})
            current_description_lines = []
        else:
            if len(line) > 1:
                current_description_lines.append(line)
    parsed_data["line_items"] = line_items
    
    # --- Stage 3: Vendor and Date Extraction ---
    if lines:
        for line in lines[:5]:
            if len(line) > 3 and line.upper() == line and not any(kw in line.lower() for kw in ["invoice", "facture", "date", "caissier"]):
                parsed_data["vendor"] = line
                break
    
    date_pattern = r'(\d{4}[-/\s]\d{1,2}[-/\s]\d{1,2})|(\d{1,2}[-/\s]\d{1,2}[-/\s]\d{2,4})'
    if date_match := re.search(date_pattern, text):
        parsed_data["date"] = date_match.group(0).strip()
    
    # Final fallback for total if keyword search failed
    if parsed_data["total_amount"] == 0.0:
        all_amounts = [float(m.replace(',', '.')) for m in re.findall(r'(\d+[.,]\d{2})', text)]
        if all_amounts:
            parsed_data["total_amount"] = max(all_amounts)
            
    return parsed_data

def extract_and_parse_file(uploaded_file):
    """Main pipeline function using Google Vision."""
    try:
        raw_text = extract_text_from_file(uploaded_file)
        if "Error" in raw_text or "Unsupported" in raw_text:
             return raw_text, {"error": raw_text}
        parsed_data = parse_ocr_text(raw_text)
        return raw_text, parsed_data
    except Exception as e:
        error_message = f"A critical error occurred: {str(e)}"
        return error_message, {"error": error_message}
