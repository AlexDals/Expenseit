import streamlit as st
from google.cloud import vision
import google.generativeai as genai
import json

# --- GOOGLE VISION API SETUP (for OCR) ---
@st.cache_resource
def get_vision_client():
    """Initializes and returns a Google Vision API client."""
    try:
        credentials_dict = dict(st.secrets.google_credentials)
        client = vision.ImageAnnotatorClient.from_service_account_info(credentials_dict)
        return client
    except Exception as e:
        st.error(f"Could not initialize Google Vision API client: {e}")
        st.stop()

# --- GEMINI API SETUP (for Parsing) ---
@st.cache_resource
def get_gemini_client():
    """Initializes and returns a Gemini API client."""
    try:
        api_key = st.secrets.gemini.api_key
        genai.configure(api_key=api_key)
        # Using a model that is fast and capable of JSON output
        model = genai.GenerativeModel('gemini-1.5-flash')
        return model
    except Exception as e:
        st.error(f"Could not initialize Gemini API client: {e}. Please check your Streamlit secrets.")
        st.stop()


def extract_text_from_file(uploaded_file):
    """Extracts text from a file using Google Cloud Vision AI."""
    client = get_vision_client()
    file_bytes = uploaded_file.getvalue()
    try:
        image = vision.Image(content=file_bytes)
        response = client.document_text_detection(image=image)
        if response.error.message:
            raise Exception(f"{response.error.message}")
        return response.full_text_annotation.text
    except Exception as e:
        return f"Error calling Google Vision API: {str(e)}"

# --- DEFINITIVE AI-POWERED PARSING LOGIC ---
def parse_text_with_gemini(ocr_text: str):
    """Uses Gemini to parse raw OCR text into a structured dictionary."""
    model = get_gemini_client()

    # This prompt is the "brain" of our parser. It instructs the AI on exactly what to do.
    prompt = f"""
    You are an expert expense analyst. Your task is to accurately extract structured information from the provided OCR text of a receipt.

    INSTRUCTIONS:
    1.  Analyze the entire receipt text provided below.
    2.  Extract the following fields: vendor, date, total_amount, gst_amount, pst_amount, and all distinct line_items.
    3.  For 'vendor', find the main store or company name. It's often at the top and in all caps.
    4.  For 'date', find the primary date of the transaction.
    5.  For 'total_amount', find the final grand total paid.
    6.  For 'gst_amount' and 'pst_amount', find the amounts explicitly labeled with 'GST'/'TPS' and 'PST'/'TVQ' respectively.
    7.  For 'line_items', extract all individual products or services. Each line item must have a 'description' and a 'price'. Do not include taxes, subtotals, or totals as line items.
    8.  Return the data as a single, valid JSON object. Do not include any text or formatting outside of the JSON. If a value is not found, set it to 0.0 for numerical fields and null for text fields. The line_items should be an array of objects.

    RECEIPT TEXT:
    ---
    {ocr_text}
    ---

    JSON OUTPUT:
    """
    
    try:
        # Configure the model to output JSON
        generation_config = genai.GenerationConfig(response_mime_type="application/json")
        response = model.generate_content(prompt, generation_config=generation_config)
        
        # Load the JSON string from the model's response into a Python dictionary
        parsed_data = json.loads(response.text)
        return parsed_data

    except Exception as e:
        st.error(f"Error parsing receipt with AI model: {e}")
        # Return a default structure on error so the app doesn't crash
        return {"vendor": "Error", "date": None, "total_amount": 0.0, "gst_amount": 0.0, "pst_amount": 0.0, "hst_amount": 0.0, "line_items": []}


# --- Main Entry Point Function ---
def extract_and_parse_file(uploaded_file):
    """Main pipeline function using Google Vision for OCR and Gemini for parsing."""
    try:
        # Step 1: Get high-quality OCR text from Google Vision
        raw_text = extract_text_from_file(uploaded_file)
        if "Error" in raw_text:
             return raw_text, {"error": raw_text}
        
        # Step 2: Use Gemini to parse the clean text into structured data
        parsed_data = parse_text_with_gemini(raw_text)
        return raw_text, parsed_data
        
    except Exception as e:
        error_message = f"A critical error occurred: {str(e)}"
        return error_message, {"error": error_message}
