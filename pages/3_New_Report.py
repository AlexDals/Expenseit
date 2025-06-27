import streamlit as st
from utils.nav_utils import filter_pages_by_role
filter_pages_by_role()

import pandas as pd
from datetime import date
from utils import ocr_utils, supabase_utils as su

st.set_page_config(layout="wide", page_title="Create New Expense Report")

# --- Authentication Guard ---
if not st.session_state.get("authentication_status"):
    st.warning("Please log in to access this page.")
    st.stop()

username = st.session_state.get("username")
user_id  = st.session_state.get("user_id")
st.session_state.setdefault("current_report_items", [])

# Load categories
try:
    cats = su.get_all_categories()
    cat_names = [""] + [c["name"] for c in cats]
    cat_map   = {c["name"]: c["id"] for c in cats}
except Exception as e:
    st.error(f"Could not load categories: {e}")
    cats, cat_names, cat_map = [], [""], {}

report_name = st.text_input("Report Name/Purpose*", placeholder="e.g., Office Supplies - June")
uploaded = st.file_uploader("Upload Receipt (Image/PDF)", type=["png","jpg","jpeg","pdf"])

parsed, raw_text, path_db = {}, "", None
st.session_state.setdefault("edited_line_items", [])

if uploaded:
    with st.spinner("Processing..."):
        raw_text, parsed = ocr_utils.extract_and_parse_file(uploaded)
        if parsed.get("error"):
            st.error(parsed["error"])
            parsed = {}
        else:
            st.success("OCR complete.")
        path_db = su.upload_receipt(uploaded, username)
        if path_db:
            st.success("Receipt uploaded.")

line_items = parsed.get("line_items", [])
if line_items:
    df = pd.DataFrame(line_items)
    if "category" not in df.columns:
        df["category"] = ""
    df = st.data_editor(
        df,
        column_config={
            "category": st.column_config.SelectboxColumn("Category", options=cat_names),
            "price":    st.column_config.NumberColumn("Price", format="$%.2f")
        },
        hide_index=True,
        key="line_editor"
    )
    st.session_state.edited_line_items = df.to_dict("records")
else:
    st.session_state.edited_line_items = []

with st.form("item_form"):
    st.write("Verify extracted data")
    overall_cat = st.selectbox("Overall Category*", options=cat_names)
    currency    = st.radio("Currency*", ["CAD","USD"], horizontal=True)
    col1, col2  = st.columns(2)
    with col1:
        parsed_date = pd.to_datetime(parsed.get("date"), errors="coerce")
        d0 = date.today() if pd.isna(parsed_date) else parsed_date.date()
        exp_date    = st.date_input("Expense Date", value=d0)
        vendor      = st.text_input("Vendor Name", value=parsed.get("vendor",""))
        desc        = st.text_area("Purpose/Description")
    with col2:
        amt     = st.number_input("Amount (Total)", min_value=0.01, value=float(parsed.get("total_amount",0.0)))
        st.markdown("###### Taxes")
        t1, t2, t3 = st.columns(3)
        gst = t1.number_input("GST/TPS", value=float(parsed.get("gst_amount",0.0)))
        pst = t2.number_input("PST/QST", value=float(parsed.get("pst_amount",0.0)))
        hst = t3.number_input("HST/TVH", value=float(parsed.get("hst_amount",0.0)))

    if st.form_submit_button("Add This Expense to Report"):
        if vendor and amt>0 and overall_cat:
            items = st.session_state.edited_line_items
            for it in items:
                it["category_id"]   = cat_map.get(it.get("category"))
                it["category_name"] = it.get("category")
            new = {
                "date": exp_date, "vendor": vendor, "description": desc,
                "amount": amt, "category_id": cat_map.get(overall_cat),
                "currency": currency, "receipt_path": path_db,
                "ocr_text": raw_text, "gst_amount": gst, "pst_amount": pst,
                "hst_amount": hst, "line_items": items
            }
            st.session_state.current_report_items.append(new)
            st.success(f"Added expense '{vendor}'.")
        else:
            st.error("Fill Vendor, Amount & Category.")

if st.session_state.current_report_items:
    st.markdown("---")
    st.subheader("Current Report Items")
    df0 = pd.DataFrame(st.session_state.current_report_items)
    st.dataframe(df0[["date","vendor","description","amount"]])
    total = df0["amount"].sum()
    st.metric("Total Report Amount", f"${total:,.2f}")
    if st.button("Submit Entire Report"):
        if not report_name:
            st.error("Please name the report.")
        else:
            rid = su.add_report(user_id, report_name, total)
            if rid:
                ok = True
                for it in st.session_state.current_report_items:
                    if not su.add_expense_item(
                        rid, it["date"], it["vendor"], it["description"], it["amount"],
                        it["currency"], it["category_id"], it["receipt_path"],
                        it["ocr_text"], it["gst_amount"], it["pst_amount"],
                        it["hst_amount"], it["line_items"]
                    ):
                        ok = False
                        break
                if ok:
                    st.success(f"Report '{report_name}' submitted!")
                    st.session_state.current_report_items = []
                else:
                    st.error("Error saving items.")
            else:
                st.error("Error creating report.")
