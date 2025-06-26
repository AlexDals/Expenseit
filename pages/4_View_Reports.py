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
    generate_report_xml,
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

# Build dropdown with "filed by" labels
labels = []
for rpt in reports:
    rpt_name = rpt.get("report_name", "Untitled")
    filer = "Unknown"
    user_obj = rpt.get("user")
    if isinstance(user_obj, dict) and user_obj.get("name"):
        filer = user_obj["name"]
    else:
        uid = rpt.get("user_id")
        if uid is not None:
            usr = get_single_user_details(uid)
            filer = usr.get("name", "Unknown") if usr else "Unknown"
    labels.append(f"{rpt_name} (filed by {filer})")

selected_label = st.selectbox("Select a report", labels, index=0)
report = reports[labels.index(selected_label)]

# Fetch expense items for that report
items_df = get_expenses_for_report(report["id"])

# Display only the core columns, dynamically handling column names
if not items_df.empty:
    cols = list(items_df.columns)
    # Determine date column
    for c in ("date", "expense_date", "created_at"):
        if c in cols:
            date_col = c
            break
    else:
        date_col = cols[0]
    vendor_col = "vendor" if "vendor" in cols else (cols[1] if len(cols) > 1 else date_col)
    desc_col = "description" if "description" in cols else (cols[2] if len(cols) > 2 else vendor_col)
    amt_col = "amount" if "amount" in cols else ("total_amount" if "total_amount" in cols else (cols[3] if len(cols) > 3 else desc_col))

    display_df = items_df[[date_col, vendor_col, desc_col, amt_col]].rename(columns={
        date_col: "Date",
        vendor_col: "Vendor",
        desc_col: "Description",
        amt_col: "Amount",
    })
    st.dataframe(display_df)
else:
    st.write("No expense items found for this report.")

# Generate XML and ensure bytes for download
xml_data = generate_report_xml(report, items_df)
xml_bytes = xml_data.encode("utf-8") if isinstance(xml_data, str) else xml_data
clean_name = report.get("report_name", "report").replace(" ", "_")

st.download_button(
    label="💿 Download as XML",
    data=xml_bytes,
    file_name=f"{clean_name}.xml",
    mime="application/xml",
    use_container_width=True,
)

# Bundle receipts into ZIP
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
                fname = path.split("/")[-1]
                zf.writestr(fname, file_bytes)
        except Exception:
            pass

zip_buffer.seek(0)
st.download_button(
    label="📦 Download Receipts ZIP",
    data=zip_buffer.read(),
    file_name=f"{clean_name}_receipts.zip",
    mime="application/zip",
    use_container_width=True,
)
