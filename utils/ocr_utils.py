import pytesseract
from PIL import Image
import io
import re
import fitz  # PyMuPDF
import cv2  # OpenCV
import numpy as np
import pandas as pd

# --- IMAGE PREPROCESSING AND TEXT EXTRACTION (No changes) ---
def preprocess_image(image_bytes):
    img_array = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                   cv2.THRESH_BINARY, 11, 2)
    _, processed_img_bytes = cv2.imencode('.png', thresh)
    return processed_img_bytes.tobytes()

def get_structured_data_from_image(image_bytes) -> pd.DataFrame:
    processed_bytes = preprocess_image(image_bytes)
    image = Image.open(io.BytesIO(processed_bytes))
    config = r'--oem 3 --psm 3'
    data_df = pytesseract.image_to_data(image, config=config, output_type=pytesseract.Output.DATAFRAME)
    data_df = data_df[data_df.conf > 40]
    data_df['text'] = data_df['text'].str.strip()
    data_df = data_df.dropna(subset=['text'])
    data_df = data_df[data_df.text != '']
    return data_df

# --- DEFINITIVE PARSING LOGIC ---
def parse_invoice_with_geometry(df_list: list[pd.DataFrame]):
    parsed_data = {"vendor": "N/A", "date": "N/A", "total_amount": 0.0, "gst_amount": 0.0, "pst_amount": 0.0, "hst_amount": 0.0}
    
    if not df_list: return parsed_data
    
    full_df = pd.concat(df_list, ignore_index=True)
    full_df['text_lower'] = full_df['text'].str.lower()

    # --- Find All Monetary Values ---
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

    def find_value_in_column(header_area, candidates_df):
        if not header_area: return 0.0
        x_min, y_min, x_max, _ = header_area
        col_center = x_min + (x_max - x_min) / 2
        best_match = 0.0
        smallest_distance = float('inf')

        for _, row in candidates_df.iterrows():
            if row['top'] > y_min:
                row_center = row['left'] + row['width'] / 2
                if abs(row_center - col_center) < (row['width'] / 2 + (x_max - x_min) / 2 + 35):
                    vertical_distance = row['top'] - y_min
                    if vertical_distance < smallest_distance:
                        smallest_distance = vertical_distance
                        best_match = row['amount']
        return best_match

    # --- Find Anchors and Basic Info ---
    all_amounts = money_df['amount'].tolist()
    
    # Use positional analysis for key values
    federal_coords = find_keyword_area(full_df, ["federal", "fédérale", "gst", "tps"])
    total_coords = find_keyword_area(full_df, ["total payable", "payer", "invoice total"])
    
    parsed_data["gst_amount"] = find_value_in_column(federal_coords, money_df)
    parsed_data["total_amount"] = find_value_in_column(total_coords, money_df)

    # Fallback for total if positional search fails
    if parsed_data["total_amount"] == 0.0 and all_amounts:
        parsed_data["total_amount"] = max(all_amounts)

    # Find Subtotal by looking for keywords and ensuring it's not the total
    subtotal = 0.0
    subtotal_keywords = ["subtotal", "sous-total", "total partiel", "(excl. tax)"]
    for line in " \n ".join(full_df['text'].dropna()).split('\n'):
        if any(kw in line.lower() for kw in subtotal_keywords):
            line_amounts = [float(m.group(1).replace(',', '.')) for m in re.finditer(r'[$€£]?\s*(\d+[.,]\d{2})', line)]
            for amt in line_amounts:
                if amt != parsed_data["total_amount"]:
                    subtotal = max(subtotal, amt)

    # --- NEW: Deductive Reasoning for Missing Tax ---
    grand_total = parsed_data["total_amount"]
    gst = parsed_data["gst_amount"]

    if grand_total > 0 and subtotal > 0 and gst > 0 and parsed_data["pst_amount"] == 0.0:
        # Calculate what the second tax *should* be
        expected_pst = round(grand_total - subtotal - gst, 2)
        
        # Confirm this calculated number actually exists on the receipt to avoid errors
        if not money_df[abs(money_df['amount'] - expected_pst) < 0.02].empty:
            parsed_data["pst_amount"] = expected_pst
            
    # --- Final Cleanup ---
    for line in " \n ".join(full_df['text'].dropna()).split('\n'):
        if line.lower().strip().startswith("sold by / vendu par:"):
            parsed_data["vendor"] = line.split(":", 1)[1].strip()
            break
    
    date_pattern = r'(?i)(?:Date|Invoice Date)[:\s]*(\d{1,2}[-/.\s]+\w+[-/.\s]+\d{2,4}|\w+[-/.\s]+\d{1,2}[,.\s]+\d{2,4})'
    if date_match := re.search(date_pattern, " ".join(full_df['text'].dropna())):
        parsed_data["date"] = date_match.group(1).strip()

    return parsed_data

# --- Main Entry Point Function ---
def extract_and_parse_file(uploaded_file):
    try:
        file_bytes = uploaded_file.getvalue()
        df_list, raw_text = [], ""

        if uploaded_file.type == "application/pdf":
            with fitz.open(stream=file_bytes, filetype="pdf") as doc:
                for page in doc:
                    pix = page.get_pixmap(dpi=300)
                    img_bytes = pix.tobytes("png")
                    df_list.append(get_structured_data_from_image(img_bytes))
        elif uploaded_file.type in ["image/png", "image/jpeg", "image/jpg"]:
            df_list.append(get_structured_data_from_image(file_bytes))
        else:
            return "Unsupported file type", {"error": "Unsupported file type"}
        
        if not df_list:
            return "No text could be extracted.", {"error": "Could not extract any data from the file."}

        for df in df_list:
            raw_text += " \n ".join(df['text'].dropna()) + "\n--- Page ---\n"
            
        parsed_data = parse_invoice_with_geometry(df_list)
        return raw_text, parsed_data
        
    except Exception as e:
        error_message = f"A critical error occurred: {str(e)}"
        return error_message, {"error": error_message}
