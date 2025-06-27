# File: pages/3_New_Report.py

import streamlit as st
from utils import ocr_utils, supabase_utils as su
import pandas as pd
from datetime import date
from utils.ui_utils import hide_streamlit_pages_nav

# *First thing* on the page:
hide_streamlit_pages_nav()

st.set_page_config(layout="wide", page_title="Create New Expense Report")

# --- Authentication Guard ---
if not st.session_state.get("authentication_status"):
    st.warning("Please log in to access this page.")
    st.stop()

username = st.session_state.get("username")
user_id  = st.session_state.get("user_id")
if not user_id:
    st.error("User profile not found in session.")
    st.stop()

if 'current_report_items' not in st.session_state:
    st.session_state.current_report_items = []

# Load categories
try:
    cats = su.get_all_categories()
    cat_names = [""] + [c["name"] for c in cats]
    cat_map   = {c["name"]: c["id"] for c in cats}
except Exception as e:
    st.error(f"Could not load categories: {e}")
    cats, cat_names, cat_map = [], [""], {}

report_name = st.text_input("Report Name/Purpose*", placeholder="e.g., Office Supplies - June")
uploaded = st.file_uploader("Upload Receipt (Image or PDF)", type=["png", "jpg", "jpeg", "pdf"])

parsed, raw_text, path_db = {}, "", None
if 'edited_line_items' not in st.session_state:
    st.session_state.edited_line_items = []

if uploaded:
    with st.spinner("Processing OCR and uploading receipt..."):
        raw_text, parsed = ocr_utils.extract_and_parse_file(uploaded)
        with st.expander("View Raw Extracted Text"):
            st.text_area("OCR Output", raw_text, height=300)
        if parsed.get("error"):
            st.error(parsed["error"])
            parsed = {}
        else:
            st.success("OCR processing complete.")
        path_db = su.upload_receipt(uploaded, username)
        if path_db:
            st.success("Receipt uploaded successfully!")
        else:
            st.error("Failed to upload receipt.")
else:
    parsed = {"date": None, "vendor": "", "total_amount": 0.0,
              "gst_amount": 0.0, "pst_amount": 0.0, "hst_amount": 0.0,
              "line_items": []}

line_items = parsed.get("line_items", [])
if line_items:
    df = pd.DataFrame(line_items)
    if "category" not in df.columns:
        df["category"] = ""
    df = st.data_editor(
        df,
        column_config={
            "category": st.column_config.SelectboxColumn("Category", options=cat_names, required=False),
            "price":    st.column_config.NumberColumn("Price", format="$%.2f")
        },
        hide_index=True,
        key="line_item_editor"
    )
    st.session_state.edited_line_items = df.to_dict("records")

with st.form("expense_item_form"):
    st.write("Verify the extracted data below.")
    overall_cat = st.selectbox("Overall Expense Category*", options=cat_names)
    currency    = st.radio("Currency*", ["CAD", "USD"], horizontal=True)

    col1, col2 = st.columns(2)
    with col1:
        parsed_date = pd.to_datetime(parsed.get("date"), errors="coerce")
        init_date   = date.today() if pd.isna(parsed_date) else parsed_date.date()
        expense_date = st.date_input("Expense Date", value=init_date)
        vendor       = st.text_input("Vendor Name", value=parsed.get("vendor", ""))
        description  = st.text_area("Purpose/Description", placeholder="e.g., Monthly office supplies")
    with col2:
        ocr_amt = float(parsed.get("total_amount", 0.0))
        initial  = max(0.01, ocr_amt)
        amount   = st.number_input("Amount (Total)", min_value=0.01, value=initial, format="%.2f")
        st.markdown("###### Taxes (Editable)")
        t1, t2, t3 = st.columns(3)
        with t1:
            gst = st.number_input("GST/TPS", min_value=0.0, value=float(parsed.get("gst_amount", 0.0)), format="%.2f")
        with t2:
            pst = st.number_input("PST/QST", min_value=0.0, value=float(parsed.get("pst_amount", 0.0)), format="%.2f")
        with t3:
            hst = st.number_input("HST/TVH", min_value=0.0, value=float(parsed.get("hst_amount", 0.0)), format="%.2f")

    if st.form_submit_button("Add This Expense to Report"):
        if vendor and amount > 0 and overall_cat:
            items = st.session_state.get("edited_line_items", [])
            for it in items:
                it["category_id"]   = cat_map.get(it.get("category"))
                it["category_name"] = it.get("category")
            new_item = {
                "date": expense_date, "vendor": vendor, "description": description,
                "amount": amount, "category_id": cat_map.get(overall_cat),
                "currency": currency, "receipt_path": path_db, "ocr_text": raw_text,
                "gst_amount": gst, "pst_amount": pst, "hst_amount": hst,
                "line_items": items
            }
            st.session_state.current_report_items.append(new_item)
            st.success(f"Added: '{vendor}' expense to report '{report_name}'.")
        else:
            st.error("Please fill out Vendor, Amount, and Overall Category.")

if st.session_state.current_report_items:
    st.markdown("---")
    st.subheader("Current Report Items to be Submitted")
    curr_df = pd.DataFrame(st.session_state.current_report_items)
    st.dataframe(curr_df[["date", "vendor", "description", "amount"]])
    total = curr_df["amount"].sum()
    st.metric("Total Report Amount", f"${total:,.2f}")
    if st.button("Submit Entire Report", type="primary"):
        if not report_name:
            st.error("Please provide a Report Name before submitting.")
        else:
            with st.spinner("Submitting report..."):
                report_id = su.add_report(user_id, report_name, total)
                if report_id:
                    all_ok = True
                    for it in st.session_state.current_report_items:
                        ok = su.add_expense_item(
                            report_id, it["date"], it["vendor"], it["description"],
                            it["amount"], it["currency"], it["category_id"],
                            it["receipt_path"], it["ocr_text"], it["gst_amount"],
                            it["pst_amount"], it["hst_amount"], it["line_items"]
                        )
                        if not ok:
                            all_ok = False
                            break
                    if all_ok:
                        st.success(f"Report '{report_name}' submitted successfully!")
                        st.balloons()
                        st.session_state.current_report_items = []
                    else:
                        st.error("Critical Error: Failed to save one or more items.")
                else:
                    st.error("Critical Error: Failed to create main report entry.")
