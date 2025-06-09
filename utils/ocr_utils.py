import pytesseract
from PIL import Image
import io
import re
import fitz  # PyMuPDF
import cv2  # OpenCV
import numpy as np
import pandas as pd

# --- IMAGE PREPROCESSING FUNCTION (No changes) ---
def preprocess_image(image_bytes):
    img_array = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                   cv2.THRESH_BINARY, 11, 2)
    _, processed_img_bytes = cv2.imencode('.png', thresh)
    return processed_img_bytes.tobytes()

# --- NEW CORE OCR FUNCTION: GETS STRUCTURED DATA ---
def get_structured_data_from_image(image_bytes) -> pd.DataFrame:
    """
    Performs OCR and returns a pandas DataFrame with words and their coordinates.
    """
    processed_bytes = preprocess_image(image_bytes)
    image = Image.open(io.BytesIO(processed_bytes))
    
    # Use image_to_data to get bounding box information for each word
    # PSM 6: Assume a single uniform block of text. This is often best for image_to_data
    config = r'--oem 3 --psm 6'
    data_df = pytesseract.image_to_data(
        image, 
        config=config,
        output_type=pytesseract.Output.DATAFRAME
    )
    
    # Filter out low-confidence words and non-textual elements
    data_df = data_df[data_df.conf > 30] # Use a lower confidence threshold to catch everything
    data_df['text'] = data_df['text'].str.strip()
    data_df = data_df.dropna(subset=['text'])
    data_df = data_df[data_df.text != '']
    
    return data_df

# --- NEW PARSING LOGIC: USES POSITIONAL DATA ---
def parse_ocr_data_with_position(df_list: list[pd.DataFrame]):
    """
    Parses a list of DataFrames (one per page) to find data based on X/Y position.
    """
    parsed_data = {
        "vendor": "N/A", "date": "N/A", "total_amount": 0.0,
        "gst_amount": 0.0, "pst_amount": 0.0, "hst_amount": 0.0,
    }
    
    # Combine data from all pages into one DataFrame
    full_df = pd.concat(df_list, ignore_index=True)
    full_text = " \n ".join(full_df['text'].dropna())

    # --- Basic Field Extraction (can still use regex on full text) ---
    for line in full_text.split('\n'):
        if line.lower().strip().startswith("sold by / vendu par:"):
            parsed_data["vendor"] = line.split(":", 1)[1].strip()
            break
            
    date_pattern = r'(?i)(?:Date|Invoice Date)[:\s]*(\d{1,2}[-/.\s]+\w+[-/.\s]+\d{2,4}|\w+[-/.\s]+\d{1,2}[,.\s]+\d{2,4}|\d{4}[-/]\d{2}[-/]\d{2}|\d{2}[-/]\d{2}[-/]\d{4})'
    if date_match := re.search(date_pattern, full_text):
        parsed_data["date"] = date_match.group(1).strip()

    # --- Positional Extraction Logic ---
    
    def find_header_coords(df, keywords):
        """Finds the bounding box of the first keyword found."""
        for keyword in keywords:
            header_df = df[df['text'].str.contains(keyword, case=False, na=False)]
            if not header_df.empty:
                # Return the coordinates of the first match
                header = header_df.iloc[0]
                return header['left'], header['top'], header['width'], header['height']
        return None, None, None, None

    def find_value_in_column(df, header_coords):
        """Finds the first monetary value vertically aligned under a header."""
        if header_coords[0] is None:
            return 0.0
            
        header_left, header_top, header_width, _ = header_coords
        column_x_start = header_left
        column_x_end = header_left + header_width
        
        # Find all monetary values in the DataFrame
        money_pattern = r'^\$?(\d+[.,]\d{2})$'
        money_df = df[df['text'].str.match(money_pattern, na=False)]
        
        for _, row in money_df.iterrows():
            # Check if the word is below the header and horizontally aligned
            word_left = row['left']
            word_top = row['top']
            word_center = word_left + row['width'] / 2
            
            if word_top > header_top and column_x_start - 20 < word_center < column_x_end + 20: # 20px tolerance
                try:
                    return float(row['text'].replace('$', '').replace(',', '.'))
                except (ValueError, TypeError):
                    continue
        return 0.0

    # Define keywords for each column header we're looking for
    federal_tax_keywords = ["Federal", "fédérale", "GST", "TPS"]
    provincial_tax_keywords = ["Provincial", "provinciale", "QST", "TVQ"]
    total_keywords = ["Total payable", "payer", "Invoice total"]

    # Find coordinates of headers
    federal_coords = find_header_coords(full_df, federal_tax_keywords)
    provincial_coords = find_header_coords(full_df, provincial_tax_keywords)
    total_coords = find_header_coords(full_df, total_keywords)
    
    # Find values in those columns
    parsed_data["gst_amount"] = find_value_in_column(full_df, federal_coords)
    parsed_data["pst_amount"] = find_value_in_column(full_df, provincial_coords)
    parsed_data["total_amount"] = find_value_in_column(full_df, total_coords)
    
    # Fallback for total if the column method fails
    if parsed_data["total_amount"] == 0.0:
        all_amounts = [float(m.group(1).replace(',', '.')) for m in re.finditer(r'[$€£]?\s*(\d+[.,]\d{2})', full_text)]
        if all_amounts:
            parsed_data["total_amount"] = max(all_amounts)
            
    return parsed_data

# --- Main Entry Point Function ---
def extract_and_parse_file(uploaded_file):
    """
    Top-level function that orchestrates the entire OCR and parsing pipeline.
    """
    try:
        file_bytes = uploaded_file.getvalue()
        df_list = []

        if uploaded_file.type == "application/pdf":
            with fitz.open(stream=file_bytes, filetype="pdf") as doc:
                for page in doc:
                    pix = page.get_pixmap(dpi=300)
                    img_bytes = pix.tobytes("png")
                    page_df = get_structured_data_from_image(img_bytes)
                    df_list.append(page_df)
        
        elif uploaded_file.type in ["image/png", "image/jpeg", "image/jpg"]:
            page_df = get_structured_data_from_image(file_bytes)
            df_list.append(page_df)
        
        else:
            return {"error": "Unsupported file type"}
        
        if not df_list:
            return {"error": "Could not extract any data from the file."}

        return parse_ocr_data_with_position(df_list)
            
    except Exception as e:
        return {"error": f"A critical error occurred: {str(e)}"}
