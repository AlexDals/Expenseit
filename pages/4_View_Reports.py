# File: pages/4_View_Reports.py

import streamlit as st
import pandas as pd
import io
import zipfile
import os

from utils import supabase_utils as su
from utils.nav_utils import PAGES_FOR_ROLES
from utils.ui_utils import hide_streamlit_pages_nav

# Page configuration
st.set_page_config(page_title="View Reports", layout="wide")

# Hide built-in nav & apply global CSS
hide_streamlit_pages_nav()

# --- Sidebar Navigation (role-based) ---
role = st.session_state.get("role", "logged_out")
st.sidebar.header("Navigation")
for label, fname in PAGES_FOR_ROLES.get(role, PAGES_FOR_ROLES["logged_out"]):
    if fname in ("7_Add_User.py", "8_Edit_User.py"):
        continue
    if st.sidebar.button(label):
        st.switch_page(f"pages/{fname}")

# --- Authentication Guard ---
if not st.session_state.get("authentication_status"):
    st.warning("Please log in to access this page.")
    st.stop()

# Load all reports (admin sees all; approver/user logic can be layered if needed)
try:
    all_reports = su.get_all_reports()
except Exception as e:
    st.error(f"Error loading reports: {e}")
    st.stop()

if all_reports.empty:
    st.info("No reports found.")
    st.stop()

# Select a report
report_choices = [
    f"{r['report_name']} (by {r.get('user',{}).get('name','Unknown')})"
    for r in all_reports.to_dict("records")
]
selection = st.selectbox("Select a report", report_choices)
report = all_reports.to_dict("records")[report_choices.index(selection)]

# Fetch expenses for the report
try:
    df = su.get_expenses_for_report(report["id"])
except Exception as e:
    st.error(f"Error loading expense items: {e}")
    st.stop()

# Display expense summary
st.subheader("Expense Items")
if not df.empty:
    st.dataframe(
        df[["expense_date", "vendor", "description", "amount", "gst_amount", "pst_amount", "hst_amount"]]
        .rename(columns={
            "expense_date": "Date",
            "vendor": "Vendor",
            "description": "Description",
            "amount": "Amount",
            "gst_amount": "GST",
            "pst_amount": "PST",
            "hst_amount": "HST"
        })
    )
else:
    st.write("No expense items for this report.")

# Line-items breakdown
st.subheader("Line Items Breakdown")
for _, row in df.iterrows():
    date = row["expense_date"]
    vendor = row["vendor"]
    with st.expander(f"{date} – {vendor}"):
        raw_li = row.get("line_items", [])
        if isinstance(raw_li, str):
            try:
                raw_li = pd.read_json(raw_li) if raw_li.strip().startswith('[') else []
            except:
                raw_li = []
        if not raw_li:
            st.write("No line items")
        else:
            li_df = pd.DataFrame(raw_li)
            cats = su.get_all_categories()
            cmap = {c["id"]: {"name": c["name"], "gl": c.get("gl_account","")} for c in cats}
            li_df["Category"]     = li_df["category_id"].map(lambda i: cmap.get(i, {}).get("name",""))
            li_df["GL Account #"] = li_df["category_id"].map(lambda i: cmap.get(i, {}).get("gl",""))
            st.dataframe(
                li_df.rename(columns={"description": "Line Description", "price": "Line Price"})[
                    ["Line Description", "Line Price", "Category", "GL Account #"]
                ]
            )

# --- Export Options ---
col_download_excel, col_download_zip = st.columns(2)

with col_download_excel:
    if st.button("Download as Excel"):
        to_excel = io.BytesIO()
        with pd.ExcelWriter(to_excel, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Expenses")
            # Write line items sheet too
            all_li = []
            for _, row in df.iterrows():
                raw_li = row.get("line_items", [])
                if isinstance(raw_li, str):
                    try:
                        raw_li = pd.read_json(raw_li) if raw_li.strip().startswith('[') else []
                    except:
                        raw_li = []
                for item in raw_li:
                    item_record = item.copy()
                    item_record["expense_id"] = row["id"]
                    all_li.append(item_record)
            li_df = pd.DataFrame(all_li)
            li_df.to_excel(writer, index=False, sheet_name="LineItems")
        to_excel.seek(0)
        st.download_button(
            label="Download .xlsx",
            data=to_excel,
            file_name=f"{report['report_name'].replace(' ','_')}.xlsx"
        )

with col_download_zip:
    if st.button("Download Receipts (ZIP)"):
        supabase = su.init_connection()
        # Collect receipt files
        receipt_paths = df["receipt_path"].dropna().unique().tolist()
        if not receipt_paths:
            st.error("No receipts uploaded for this report.")
        else:
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w") as zf:
                for path in receipt_paths:
                    try:
                        content = supabase.storage.from_("receipts").download(path)
                        filename = os.path.basename(path)
                        zf.writestr(filename, content)
                    except Exception as ex:
                        st.warning(f"Could not include '{path}': {ex}")
            zip_buffer.seek(0)
            st.download_button(
                label="Download Receipts ZIP",
                data=zip_buffer,
                file_name=f"{report['report_name'].replace(' ','_')}_receipts.zip"
            )
