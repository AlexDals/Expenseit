import pytesseract
from PIL import Image
import io
import re
import fitz  # PyMuPDF
import cv2  # OpenCV
import numpy as np
import pandas as pd

# --- IMAGE PREPROCESSING (No changes) ---
def preprocess_image(image_bytes):
    img_array = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                   cv2.THRESH_BINARY, 11, 2)
    _, processed_img_bytes = cv2.imencode('.png', thresh)
    return processed_img_bytes.tobytes()

# --- NEW CORE OCR FUNCTION: GETS DATAFRAME WITH COORDINATES ---
def get_structured_data_from_image(image_bytes) -> pd.DataFrame:
    processed_bytes = preprocess_image(image_bytes)
    image = Image.open(io.BytesIO(processed_bytes))
    
    # Use image_to_data to get bounding boxes. PSM 3 or 11 are good for this.
    config = r'--oem 3 --psm 3'
    data_df = pytesseract.image_to_data(image, config=config, output_type=pytesseract.Output.DATAFRAME)
    
    # Clean up the DataFrame
    data_df = data_df[data_df.conf > 40] # Keep words with confidence > 40
    data_df['text'] = data_df['text'].str.strip()
    data_df = data_df.dropna(subset=['text'])
    data_df = data_df[data_df.text != '']
    return data_df

# In utils/ocr_utils.py, replace the existing parse_invoice_with_geometry function.
# The other functions in the file do not need to change.

def parse_invoice_with_geometry(df_list: list[pd.DataFrame]):
    parsed_data = {"vendor": "N/A", "date": "N/A", "total_amount": 0.0, "gst_amount": 0.0, "pst_amount": 0.0, "hst_amount": 0.0}
    
    if not df_list: return parsed_data
    
    full_df = pd.concat(df_list, ignore_index=True)
    full_df['text_lower'] = full_df['text'].str.lower()

    # --- Find Monetary Values ---
    money_pattern = r'^\$?(\d{1,3}(?:,\d{3})*[.,]\d{2})$'
    money_df = full_df[full_df['text'].str.match(money_pattern, na=False)].copy()
    money_df['amount'] = money_df['text'].str.replace(r'[$,]', '', regex=True).astype(float)

    # --- Find Keywords and their Coordinates ---
    def find_keyword_area(df, keywords):
        for keyword in keywords:
            keyword_df = df[df['text_lower'].str.contains(keyword, na=False)]
            if not keyword_df.empty:
                k = keyword_df.iloc[0]
                return (k['left'], k['top'], k['left'] + k['width'], k['top'] + k['height'])
        return None

    # --- Associate values to headers based on vertical alignment ---
    def find_value_in_column(header_area, candidates_df):
        if not header_area: return 0.0, None
        x_min, y_min, x_max, _ = header_area
        col_center = x_min + (x_max - x_min) / 2
        
        best_match_row = None
        smallest_distance = float('inf')

        for index, row in candidates_df.iterrows():
            if row['top'] > y_min:
                row_center = row['left'] + row['width'] / 2
                if abs(row_center - col_center) < (row['width'] / 2 + (x_max - x_min) / 2 + 35): # 35px tolerance
                    vertical_distance = row['top'] - y_min
                    if vertical_distance < smallest_distance:
                        smallest_distance = vertical_distance
                        best_match_row = row
        
        return (best_match_row['amount'], best_match_row) if best_match_row is not None else (0.0, None)

    # --- UPDATED BILINGUAL KEYWORD LISTS ---
    federal_tax_keywords = ["federal", "fédérale", "gst", "tps"]
    provincial_tax_keywords = ["provincial", "provinciale", "pst", "rst", "qst", "tvp", "tvd", "tvq"]
    hst_keywords = ["hst", "tvh"]
    total_keywords = ["total payable", "total à payer", "invoice total", "total de la facture"]

    # Find coordinates of headers
    federal_coords = find_keyword_area(full_df, federal_tax_keywords)
    provincial_coords = find_keyword_area(full_df, provincial_tax_keywords)
    hst_coords = find_keyword_area(full_df, hst_keywords)
    total_coords = find_keyword_area(full_df, total_keywords)
    
    # Find values in those columns
    gst_amount, gst_row = find_value_in_column(federal_coords, money_df)
    pst_amount, _ = find_value_in_column(provincial_coords, money_df)
    hst_amount, _ = find_value_in_column(hst_coords, money_df)
    total_amount, _ = find_value_in_column(total_coords, money_df)
    
    # Assign found values
    parsed_data["gst_amount"] = gst_amount
    parsed_data["pst_amount"] = pst_amount
    parsed_data["hst_amount"] = hst_amount
    parsed_data["total_amount"] = total_amount

    # Heuristic: If we found HST, GST/PST should be zero
    if hst_amount > 0:
        parsed_data["gst_amount"] = 0.0
        parsed_data["pst_amount"] = 0.0

    # Heuristic: Find second tax based on position of first tax (if provincial header was missed)
    if gst_amount > 0 and pst_amount == 0.0 and gst_row is not None:
        gst_top = gst_row['top']
        gst_left = gst_row['left']
        
        for _, row in money_df.iterrows():
            if abs(row['top'] - gst_top) < 10 and row['left'] > gst_left:
                if row['amount'] != gst_amount and row['amount'] != total_amount:
                    parsed_data["pst_amount"] = row['amount']
                    break

    # --- Fallbacks and Final Cleanup ---
    if parsed_data["total_amount"] == 0.0 and not money_df.empty:
        parsed_data["total_amount"] = money_df['amount'].max()
    
    full_text_for_parsing = " \n ".join(full_df['text'].dropna())
    for line in full_text_for_parsing.split('\n'):
        if line.lower().strip().startswith("sold by / vendu par:"):
            parsed_data["vendor"] = line.split(":", 1)[1].strip()
            break
    
    date_pattern = r'(?i)(?:Date|Invoice Date)[:\s]*(\d{1,2}[-/.\s]+\w+[-/.\s]+\d{2,4}|\w+[-/.\s]+\d{1,2}[,.\s]+\d{2,4})'
    if date_match := re.search(date_pattern, full_text_for_parsing):
        parsed_data["date"] = date_match.group(1).strip()

    return parsed_data

# --- Main Entry Point Function (UPDATED) ---
def extract_and_parse_file(uploaded_file):
    """
    Top-level function that orchestrates the entire positional OCR pipeline.
    """
    try:
        file_bytes = uploaded_file.getvalue()
        df_list = []
        raw_text = ""

        # Process file (image or PDF) into a list of DataFrames (one per page)
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
            return "Unsupported file type", {"error": "Unsupported file type"}
        
        if not df_list:
            return "No text could be extracted.", {"error": "Could not extract any data from the file."}

        # Combine raw text from all pages for display
        for df in df_list:
            raw_text += " \n ".join(df['text'].dropna()) + "\n--- Page ---\n"
            
        # Parse the structured data
        parsed_data = parse_invoice_with_geometry(df_list)
        return raw_text, parsed_data
        
    except Exception as e:
        error_message = f"A critical error occurred in the OCR pipeline: {str(e)}"
        return error_message, {"error": error_message}
