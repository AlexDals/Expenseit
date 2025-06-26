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

# Build dropdown with “filed by” context
labels = []
filer_map = {}
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
    filer_map[rpt["id"]] = filer

selected = st.selectbox("Select a report", labels, index=0)
report = reports[labels.index(selected)]
filer_name = filer_map[report["id"]]

# Fetch and display only the core columns
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

# Prepare base filename
base_name = report.get("report_name", "report").replace(" ", "_")

# — Export as Excel
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

# — Generate XML, guard against None
xml_data = None
try:
    report_series = pd.Series(report)
    xml_data = generate_report_xml(report_series, items_df, filer_name)
except Exception as e:
    st.error(f"Error generating XML: {e}")

if xml_data is not None:
    if isinstance(xml_data, str):
        xml_bytes = xml_data.encode("utf-8")
    elif isinstance(xml_data, bytes):
        xml_bytes = xml_data
    else:
        # fallback: convert to string then bytes
        xml_bytes = str(xml_data).encode("utf-8")
    st.download_button(
        label="💿 Download as XML",
        data=xml_bytes,
        file_name=f"{base_name}.xml",
        mime="application/xml",
        use_container_width=True,
    )
else:
    st.warning("XML export unavailable for this report.")

# — Bundle receipts into ZIP for download
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
