import streamlit as st
from utils import ocr_utils, supabase_utils as su
import pandas as pd
from datetime import date

def reset_form_state():
    """
    Clears all session state variables related to a single OCR job.
    This is called when the file uploader's value changes.
    """
    st.session_state.processing_complete = False
    st.session_state.ocr_results = {}
    st.session_state.raw_text = ""
    st.session_state.receipt_path_for_db = None
    if 'edited_line_items' in st.session_state:
        st.session_state.edited_line_items = []
    
    # NOTE: We DO NOT modify the 'receipt_uploader' key here, as this function
    # is called BY the uploader's on_change event.

# --- Authentication Guard ---
if not st.session_state.get("authentication_status"):
    st.warning("Please log in to access this page.")
    st.stop()

# --- Page Setup and Session State Initialization ---
st.title("📄 Create New Expense Report")
username = st.session_state.get("username")
user_id = st.session_state.get("user_id")

if not user_id:
    st.error("User profile not found in session. Please log in again.")
    st.stop()

if 'current_report_items' not in st.session_state:
    st.session_state.current_report_items = []
if 'ocr_results' not in st.session_state:
    st.session_state.ocr_results = {}
if 'receipt_path_for_db' not in st.session_state:
    st.session_state.receipt_path_for_db = None
if 'raw_text' not in st.session_state:
    st.session_state.raw_text = ""
if 'processing_complete' not in st.session_state:
    st.session_state.processing_complete = False
if 'edited_line_items' not in st.session_state:
    st.session_state.edited_line_items = []

# --- Main UI ---
report_name = st.text_input("Report Name/Purpose*", placeholder="e.g., Office Supplies - June")
st.subheader("Add Expense/Receipt")
uploaded_receipt = st.file_uploader(
    "Upload Receipt (Image or PDF)",
    type=["png", "jpg", "jpeg", "pdf"],
    key="receipt_uploader",
    on_change=reset_form_state
)

# --- Loop-Safe Processing Logic ---
if uploaded_receipt and not st.session_state.processing_complete:
    with st.spinner("Processing OCR and uploading receipt..."):
        raw_text, parsed_data = ocr_utils.extract_and_parse_file(uploaded_receipt)
        st.session_state.raw_text = raw_text
        st.session_state.ocr_results = parsed_data
        st.session_state.receipt_path_for_db = su.upload_receipt(uploaded_receipt, username)
        st.session_state.processing_complete = True
        st.rerun()

parsed_data = st.session_state.ocr_results
raw_text = st.session_state.raw_text
receipt_path_for_db = st.session_state.receipt_path_for_db

if raw_text:
    with st.expander("View Raw Extracted Text", expanded=True):
        st.text_area("OCR Output", raw_text, height=250)
    if parsed_data.get("error"):
        st.error(parsed_data["error"])
    else:
        st.success("OCR processing complete. Please verify the values below.")

try:
    categories = su.get_all_categories()
    category_names = [""] + [cat['name'] for cat in categories]
    category_dict = {cat['name']: cat['id'] for cat in categories}
except Exception as e:
    st.error(f"Could not load categories: {e}"); categories, category_names, category_dict = [], [""], {}

line_items_from_ocr = parsed_data.get("line_items", [])
if line_items_from_ocr:
    st.markdown("---"); st.subheader("Assign Categories to Line Items")
    df = pd.DataFrame(line_items_from_ocr)
    if 'category' not in df.columns:
        df['category'] = ""
    edited_line_items = st.data_editor(df, column_config={"category": st.column_config.SelectboxColumn("Category", options=category_names), "price": st.column_config.NumberColumn("Price", format="$%.2f")}, hide_index=True, key="line_item_editor")
    st.session_state.edited_line_items = edited_line_items.to_dict('records')

with st.form("expense_item_form"):
    st.write("Verify the extracted data below.")
    overall_category = st.selectbox("Overall Expense Category*", options=category_names)
    currency = st.radio("Currency*", ["CAD", "USD"], horizontal=True)
    col1, col2 = st.columns(2)
    with col1:
        parsed_timestamp = pd.to_datetime(parsed_data.get("date"), errors='coerce')
        initial_date = date.today() if pd.isna(parsed_timestamp) else parsed_timestamp.date()
        expense_date = st.date_input("Expense Date", value=initial_date)
        vendor = st.text_input("Vendor Name", value=parsed_data.get("vendor", ""))
        description = st.text_area("Purpose/Description", placeholder="e.g., Monthly office supplies")
    with col2:
        ocr_amount = float(parsed_data.get("total_amount", 0.0))
        initial_value = max(0.01, ocr_amount)
        amount = st.number_input("Amount (Total)", min_value=0.01, value=initial_value, format="%.2f")
        st.markdown("###### Taxes (Editable)")
        tax_col1, tax_col2, tax_col3 = st.columns(3)
        with tax_col1: gst_amount = st.number_input("GST/TPS", min_value=0.0, value=float(parsed_data.get("gst_amount", 0.0)), format="%.2f")
        with tax_col2: pst_amount = st.number_input("PST/QST", min_value=0.0, value=float(parsed_data.get("pst_amount", 0.0)), format="%.2f")
        with tax_col3: hst_amount = st.number_input("HST/TVH", min_value=0.0, value=float(parsed_data.get("hst_amount", 0.0)), format="%.2f")
    
    submitted_item = st.form_submit_button("Add This Expense to Report")
    if submitted_item:
        if vendor and amount > 0 and overall_category:
            processed_line_items = st.session_state.get('edited_line_items', [])
            for item in processed_line_items:
                cat_name = item.get('category'); item['category_id'] = category_dict.get(cat_name); item['category_name'] = cat_name
            new_item = {
                "date": expense_date, "vendor": vendor, "description": description, "amount": amount,
                "category_id": category_dict.get(overall_category), "currency": currency,
                "receipt_path": receipt_path_for_db, "ocr_text": raw_text,
                "gst_amount": gst_amount, "pst_amount": pst_amount, "hst_amount": hst_amount,
                "line_items": processed_line_items
            }
            st.session_state.current_report_items.append(new_item)
            st.success(f"Added '{vendor}' expense. The form is ready for the next receipt.")
            # We don't need to call reset here because the page will rerun and the uploader will be empty
        else:
            st.error("Please fill out Vendor, Amount, and Overall Category.")

if st.session_state.current_report_items:
    st.markdown("---"); st.subheader("Current Report Items to be Submitted")
    # ... (The rest of the file is unchanged) ...
