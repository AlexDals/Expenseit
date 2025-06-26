# File: pages/4_View_Reports.py

import streamlit as st
import pandas as pd
import io
import zipfile
from utils.supabase_utils import (
    init_connection,
    get_all_reports,
    get_report_items,
    generate_report_xml,
    get_single_user_details,
)

st.set_page_config(page_title="View Reports", layout="wide")
st.title("View Reports")

supabase = init_connection()

# Load all reports
reports = get_all_reports()
if hasattr(reports, "to_dict"):
    reports_list = reports.to_dict("records")
else:
    reports_list = reports or []

if not reports_list:
    st.info("No reports found.")
    st.stop()

# Dropdown with “filed by”
labels = []
submitter_map = {}
for rpt in reports_list:
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
    submitter_map[rpt["id"]] = filer

selected = st.selectbox("Select a report", labels, index=0)
report = reports_list[labels.index(selected)]
submitter_name = submitter_map[report["id"]]

# Fetch and display key columns of that report’s items
items = get_report_items(report["id"])
items_df = pd.DataFrame(items)
if not items_df.empty:
    # pick and rename columns
    display_df = items_df.rename(columns={
        "expense_date": "Date",
        "date": "Date",
        "vendor": "Vendor",
        "description": "Description",
        "amount": "Amount",
    })
    display_df = display_df[["Date", "Vendor", "Description", "Amount"]]
    st.dataframe(display_df)
else:
    st.write("No expense items found for this report.")

# Prepare filenames
sanitized = report.get("report_name", "report").replace(" ", "_")
xml_filename = f"{sanitized}.xml"
zip_filename = f"{sanitized}_receipts.zip"

# Generate XML and convert to bytes
try:
    xml_data = generate_report_xml(pd.Series(report), items_df, submitter_name)
    xml_bytes = xml_data.encode("utf-8") if isinstance(xml_data, str) else xml_data
    st.download_button(
        label="💿 Download as XML",
        data=xml_bytes,
        file_name=xml_filename,
        mime="application/xml",
        use_container_width=True,
    )
except Exception as e:
    st.error(f"Error generating XML: {e}")

# Build and download ZIP of receipts
zip_buf = io.BytesIO()
with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
    for itm in items:
        path = itm.get("receipt_path")
        if not path:
            continue
        try:
            resp = supabase.storage.from_("receipts").download(path)
            file_bytes = resp.get("data") if isinstance(resp, dict) else resp
            if file_bytes:
                name = path.split("/")[-1]
                zf.writestr(name, file_bytes)
        except Exception:
            continue

zip_buf.seek(0)
st.download_button(
    label="📦 Download Receipts ZIP",
    data=zip_buf.read(),
    file_name=zip_filename,
    mime="application/zip",
    use_container_width=True,
)
