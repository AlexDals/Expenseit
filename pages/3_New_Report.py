import streamlit as st
from utils import supabase_utils as su
import pandas as pd
from datetime import date

if not st.session_state.get("authentication_status"):
    st.warning("Please log in to access this page.")
    st.stop()

st.title("📄 Create New Expense Report")
username = st.session_state.get("username")
user_id = su.get_user_id_by_username(username)
if not user_id:
    st.error("Could not identify user."); st.stop()
if 'current_report_items' not in st.session_state:
    st.session_state.current_report_items = []

categories = su.get_all_categories()
category_names = [""] + [cat['name'] for cat in categories]
category_dict = {cat['name']: cat['id'] for cat in categories}

report_name = st.text_input("Report Name/Purpose*", placeholder="e.g., Office Supplies - June")
st.subheader("Add Expense/Receipt")
uploaded_receipt = st.file_uploader("Upload Receipt (Image or PDF)", type=["png", "jpg", "jpeg", "pdf"])

parsed_data, raw_text, receipt_path_for_db = {}, "", None
if 'line_item_df' not in st.session_state:
    st.session_state.line_item_df = pd.DataFrame()

if uploaded_receipt:
    # ... (OCR and file upload logic remains unchanged) ...

# --- Form for adding the expense ---
with st.form("expense_item_form"):
    st.write("Verify the extracted data below. You can assign a category to each line item.")
    
    # Fields for the overall expense
    overall_category = st.selectbox("Overall Expense Category*", options=category_names)
    currency = st.radio("Currency*", ["CAD", "USD"], horizontal=True) # NEW currency field
    
    col1, col2 = st.columns(2)
    with col1:
        # ... (date, vendor, description inputs remain the same) ...
    with col2:
        # ... (amount and tax inputs remain the same) ...

    # Line Item Category Assignment
    if not st.session_state.line_item_df.empty:
        # ... (data editor for line items remains the same) ...

    submitted_item = st.form_submit_button("Add This Expense to Report")
    if submitted_item:
        if vendor and amount > 0 and overall_category:
            processed_line_items = st.session_state.get('edited_line_items', [])
            if isinstance(processed_line_items, pd.DataFrame):
                processed_line_items = processed_line_items.to_dict('records')
            for item in processed_line_items:
                cat_name = item.get('category')
                item['category_id'] = category_dict.get(cat_name)
                item['category_name'] = cat_name
            
            new_item = {
                "date": expense_date, "vendor": vendor, "description": description, "amount": amount,
                "category_id": category_dict.get(overall_category),
                "currency": currency, # Add currency to the item data
                "receipt_path": receipt_path_for_db, "ocr_text": raw_text,
                "gst_amount": gst_amount, "pst_amount": pst_amount, "hst_amount": hst_amount,
                "line_items": processed_line_items
            }
            st.session_state.current_report_items.append(new_item)
            st.success(f"Added: '{vendor}' expense to report '{report_name}'.")
        else:
            st.error("Please fill out Vendor, Amount, and Overall Category.")

# --- Display current report items and final submission button ---
if st.session_state.current_report_items:
    # ... (this final section is updated to pass the new currency field) ...
    if st.button("Submit Entire Report", type="primary"):
        # ... (check for report_name)
        with st.spinner("Submitting report..."):
            report_id = su.add_report(user_id, report_name, total_report_amount)
            if report_id:
                all_items_saved = True
                for item in st.session_state.current_report_items:
                    success = su.add_expense_item(
                        report_id, item['date'], item['vendor'], item['description'], item['amount'],
                        item.get('currency'), # Pass the currency
                        item.get('category_id'), item.get('receipt_path'), item.get('ocr_text'),
                        item.get('gst_amount'), item.get('pst_amount'), item.get('hst_amount'),
                        item.get('line_items')
                    )
                    # ... (rest of the submission loop) ...
