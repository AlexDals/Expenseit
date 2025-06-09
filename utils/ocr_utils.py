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

# --- NEW PARSING LOGIC: GEOMETRIC ANALYSIS ---
def parse_invoice_with_geometry(df_list: list[pd.DataFrame]):
    parsed_data = {"vendor": "N/A", "date": "N/A", "total_amount": 0.0, "gst_amount": 0.0, "pst_amount": 0.0, "hst_amount": 0.0}
    full_df = pd.concat(df_list, ignore_index=True)
    full_df['text_lower'] = full_df['text'].str.lower()

    # --- Find Monetary Values ---
    money_pattern = r'^\$?(\d{1,3}(?:,\d{3})*[.,]\d{2})$'
    money_df = full_df[full_df['text'].str.match(money_pattern, na=False)].copy()
    money_df['amount'] = money_df['text'].str.replace(r'[$,]', '', regex=True).astype(float)

    # --- Find Keywords and their Coordinates ---
    def find_keyword_area(df, keywords):
        """Finds the area of the first matching keyword."""
        for keyword in keywords:
            keyword_df = df[df['text_lower'].str.contains(keyword, na=False)]
            if not keyword_df.empty:
                # Get the first match
                k = keyword_df.iloc[0]
                return (k['left'], k['top'], k['left'] + k['width'], k['top'] + k['height'])
        return None

    # Define keywords for each header
    federal_tax_keywords = ["federal", "fédérale", "gst", "tps"]
    provincial_tax_keywords = ["provincial", "provinciale", "qst", "tvq"]
    total_keywords = ["total payable", "total à payer", "invoice total"]

    # Get the coordinates for the headers
    federal_header_area = find_keyword_area(full_df, federal_tax_keywords)
    provincial_header_area = find_keyword_area(full_df, provincial_tax_keywords)
    total_header_area = find_keyword_area(full_df, total_keywords)

    # --- Associate values to headers based on vertical alignment ---
    def find_best_match_in_column(header_area, candidates_df):
        if not header_area:
            return 0.0
        
        x_min, y_min, x_max, _ = header_area
        col_center = x_min + (x_max - x_min) / 2
        
        best_match = 0.0
        smallest_distance = float('inf')

        for _, row in candidates_df.iterrows():
            # Check if the number is below the header
            if row['top'] > y_min:
                # Check horizontal alignment (center of number within column bounds)
                row_center = row['left'] + row['width'] / 2
                if abs(row_center - col_center) < (row['width'] / 2 + (x_max - x_min) / 2 + 25): # 25px tolerance
                    # Find the closest match vertically
                    vertical_distance = row['top'] - y_min
                    if vertical_distance < smallest_distance:
                        smallest_distance = vertical_distance
                        best_match = row['amount']
        return best_match

    # Find taxes by looking in the column below the headers
    parsed_data["gst_amount"] = find_best_match_in_column(federal_header_area, money_df)
    parsed_data["pst_amount"] = find_best_match_in_column(provincial_header_area, money_df)
    parsed_data["total_amount"] = find_best_match_in_column(total_header_area, money_df)

    # --- Fallbacks and Final Cleanup ---
    # If column search fails for total, use the largest number found.
    if parsed_data["total_amount"] == 0.0 and not money_df.empty:
        parsed_data["total_amount"] = money_df['amount'].max()
    
    # Basic info that doesn't need positional analysis
    for line in " \n ".join(full_df['text'].dropna()).split('\n'):
        if line.lower().strip().startswith("sold by / vendu par:"):
            parsed_data["vendor"] = line.split(":", 1)[1].strip()
            break
    
    date_pattern = r'(?i)(?:Date|Invoice Date)[:\s]*(\d{1,2}[-/.\s]+\w+[-/.\s]+\d{2,4}|\w+[-/.\s]+\d{1,2}[,.\s]+\d{2,4})'
    if date_match := re.search(date_pattern, " ".join(full_df['text'].dropna())):
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
