# File: pages/4_View_Reports.py

import streamlit as st
import pandas as pd
import io
import zipfile
from utils.supabase_utils import (
    init_connection,
    get_all_reports,
    get_single_user_details,
    get_expenses_for_report,
)

st.set_page_config(page_title="View Reports", layout="wide")
st.title("View Reports")

# Initialize Supabase
supabase = init_connection()

# Load reports
reports_df = get_all_reports()
if hasattr(reports_df, "to_dict"):
    reports = reports_df.to_dict("records")
else:
    reports = reports_df or []

if not reports:
    st.info("No reports found.")
    st.stop()

# Build dropdown with “filed by”
labels = []
for rpt in reports:
    name = rpt.get("report_name", "Untitled")
    user_obj = rpt.get("user")
    if isinstance(user_obj, dict) and user_obj.get("name"):
        filer = user_obj["name"]
    else:
        uid = rpt.get("user_id")
        if uid is not None:
            usr = get_single_user_details(uid)
            filer = usr.get("name", "Unknown") if usr else "Unknown"
        else:
            filer = "Unknown"
    labels.append(f"{name} (filed by {filer})")

selected = st.selectbox("Select a report", labels, index=0)
report = reports[labels.index(selected)]

# Fetch items and display core columns
items_df = get_expenses_for_report(report["id"])
if not items_df.empty:
    df = items_df.rename(columns={
        "expense_date": "Date",
        "date": "Date",
        "vendor": "Vendor",
        "description": "Description",
        "amount": "Amount",
    })
    display_df = df[["Date", "Vendor", "Description", "Amount"]]
    st.dataframe(display_df)
else:
    st.write("No expense items found for this report.")

# Base filename
base_name = report.get("report_name", "report").replace(" ", "_")

# Export as Excel
if not items_df.empty:
    excel_buffer = io.BytesIO()
    display_df.to_excel(excel_buffer, index=False, sheet_name="Report")
    excel_buffer.seek(0)
    st.download_button(
        label="📊 Export as Excel",
        data=excel_buffer.read(),
        file_name=f"{base_name}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

# Bundle receipts into ZIP for download
zip_buffer = io.BytesIO()
with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
    for _, row in items_df.iterrows():
        path = row.get("receipt_path")
        if not path:
            continue
        try:
            resp = supabase.storage.from_("receipts").download(path)
            file_bytes = resp.get("data") if isinstance(resp, dict) else resp
            if file_bytes:
                filename = path.split("/")[-1]
                zf.writestr(filename, file_bytes)
        except Exception:
            pass

zip_buffer.seek(0)
st.download_button(
    label="📦 Download Receipts ZIP",
    data=zip_buffer.read(),
    file_name=f"{base_name}_receipts.zip",
    mime="application/zip",
    use_container_width=True,
)
