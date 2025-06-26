# File: pages/4_View_Reports.py

import streamlit as st
import pandas as pd
import io
import zipfile
import json
from utils.supabase_utils import (
    init_connection,
    get_all_reports,
    get_single_user_details,
    get_expenses_for_report,
)

st.set_page_config(page_title="View Reports", layout="wide")
st.title("View Reports")

# Initialize Supabase client
supabase = init_connection()

# Load all reports
reports_df = get_all_reports()
if hasattr(reports_df, "to_dict"):
    reports = reports_df.to_dict("records")
else:
    reports = reports_df or []

if not reports:
    st.info("No reports found.")
    st.stop()

# Build dropdown with “filed by” labels
labels = []
for rpt in reports:
    name = rpt.get("report_name", "Untitled")
    user_obj = rpt.get("user")
    if isinstance(user_obj, dict) and user_obj.get("name"):
        filer = user_obj["name"]
    else:
        uid = rpt.get("user_id")
        filer = "Unknown"
        if uid is not None:
            usr = get_single_user_details(uid)
            filer = usr.get("name", "Unknown") if usr else "Unknown"
    labels.append(f"{name} (filed by {filer})")

selected = st.selectbox("Select a report", labels, index=0)
report = reports[labels.index(selected)]

# Fetch and display summary
items = get_expenses_for_report(report["id"])
items_df = pd.DataFrame(items)

if not items_df.empty:
    summary_df = items_df.rename(columns={
        "expense_date": "Date",
        "date": "Date",
        "vendor": "Vendor",
        "description": "Description",
        "amount": "Amount",
        "gst_amount": "GST",
        "pst_amount": "PST",
        "hst_amount": "HST",
    })
    cols = ["Date", "Vendor", "Description", "Amount", "GST", "PST", "HST"]
    st.dataframe(summary_df[cols])
else:
    st.write("No expense items found for this report.")

# Line items breakdown
st.markdown("### Line Items Breakdown")
for idx, row in items_df.iterrows():
    parent_date = row.get("date") or row.get("expense_date")
    parent_vendor = row.get("vendor")
    with st.expander(f"{parent_date} – {parent_vendor}"):
        raw_li = row.get("line_items") or []
        # If stored as JSON string, parse it
        if isinstance(raw_li, str):
            try:
                raw_li = json.loads(raw_li)
            except Exception:
                st.error("Could not parse line_items JSON")
                raw_li = []
        if not isinstance(raw_li, list):
            st.write("No line items")
            continue
        try:
            li_df = pd.DataFrame(raw_li)
            # rename columns if needed
            rename_map = {}
            if "description" in li_df.columns:
                rename_map["description"] = "Line Description"
            if "price" in li_df.columns:
                rename_map["price"] = "Line Price"
            if "category_name" in li_df.columns:
                rename_map["category_name"] = "Category"
            if "category_id" in li_df.columns:
                rename_map["category_id"] = "Category ID"
            li_df = li_df.rename(columns=rename_map)
            st.dataframe(li_df[list(rename_map.values())])
        except Exception as e:
            st.error(f"Unable to display line items: {e}")

# Prepare filenames
base = report.get("report_name", "report").replace(" ", "_")

# Export as Excel: Summary + Line Items
if not items_df.empty:
    excel_buf = io.BytesIO()
    with pd.ExcelWriter(excel_buf, engine="openpyxl") as writer:
        # Summary sheet
        summary_df[cols].to_excel(writer, index=False, sheet_name="Summary")
        # Line Items sheet
        detail_rows = []
        for _, row in items_df.iterrows():
            pl_date = row.get("date") or row.get("expense_date")
            pl_vendor = row.get("vendor")
            raw_li = row.get("line_items") or []
            if isinstance(raw_li, str):
                try:
                    raw_li = json.loads(raw_li)
                except Exception:
                    raw_li = []
            if isinstance(raw_li, list):
                for li in raw_li:
                    if not isinstance(li, dict):
                        continue
                    detail_rows.append({
                        "Parent Date":        pl_date,
                        "Parent Vendor":      pl_vendor,
                        "Parent Amount":      row.get("amount"),
                        "Line Description":   li.get("description"),
                        "Line Price":         li.get("price"),
                        "Category":           li.get("category_name") or li.get("category"),
                        "Category ID":        li.get("category_id"),
                    })
        if detail_rows:
            pd.DataFrame(detail_rows).to_excel(
                writer, index=False, sheet_name="Line Items"
            )
    excel_buf.seek(0)
    st.download_button(
        label="📊 Export as Excel",
        data=excel_buf.read(),
        file_name=f"{base}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

# Download receipts ZIP
zip_buf = io.BytesIO()
with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
    for _, row in items_df.iterrows():
        path = row.get("receipt_path")
        if not path:
            continue
        try:
            resp = supabase.storage.from_("receipts").download(path)
            file_bytes = resp.get("data") if isinstance(resp, dict) else resp
            if file_bytes:
                fname = path.split("/")[-1]
                zf.writestr(fname, file_bytes)
        except Exception:
            pass

zip_buf.seek(0)
st.download_button(
    label="📦 Download Receipts ZIP",
    data=zip_buf.read(),
    file_name=f"{base}_receipts.zip",
    mime="application/zip",
    use_container_width=True,
)
