# File: pages/4_View_Reports.py

import streamlit as st
import pandas as pd
import io
import zipfile
from utils import supabase_utils as su

st.set_page_config(page_title="View Reports", layout="wide")
st.title("View Reports")

# Initialize Supabase client
supabase = su.init_connection()

# 1) Load all reports (DataFrame or list of dicts)
reports = su.get_all_reports()
if hasattr(reports, "to_dict"):
    reports_list = reports.to_dict("records")
else:
    reports_list = reports or []

if not reports_list:
    st.info("No reports found.")
    st.stop()

# 2) Build the dropdown with the actual filer’s name
options = []
for r in reports_list:
    report_name = r.get("report_name", "Untitled")
    filer_name = "Unknown"
    # Look up the filing user’s name via their user_id
    uid = r.get("user_id") or r.get("username") or None
    if uid:
        user = su.get_single_user_details(uid)
        if user and user.get("name"):
            filer_name = user["name"]
    options.append(f"{report_name} (filed by {filer_name})")

selected = st.selectbox("Select a report", options, index=0)
report = reports_list[options.index(selected)]

# 3) Fetch and display only the core columns
items = su.get_expenses_for_report(report["id"])
items_df = pd.DataFrame(items)
if not items_df.empty:
    display_df = items_df[["date", "vendor", "description", "amount"]]
    st.dataframe(display_df)
else:
    st.write("No expense items found for this report.")

# 4) Generate XML and force it to bytes for download_button
xml_data = su.generate_report_xml(report, items)
xml_bytes = xml_data.encode("utf-8") if isinstance(xml_data, str) else xml_data
clean_name = report.get("report_name", "report").replace(" ", "_")

st.download_button(
    label="💿 Download as XML",
    data=xml_bytes,
    file_name=f"{clean_name}.xml",
    mime="application/xml",
    use_container_width=True,
)

# 5) Build a ZIP of all receipt files
zip_buf = io.BytesIO()
with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
    for item in items:
        path = item.get("receipt_path")
        if not path:
            continue
        try:
            resp = supabase.storage.from_("receipts").download(path)
            file_bytes = resp.get("data") if isinstance(resp, dict) else resp
            if file_bytes:
                fname = path.split("/")[-1]
                zf.writestr(fname, file_bytes)
        except Exception:
            # Skip any missing or failed downloads
            pass

zip_buf.seek(0)
st.download_button(
    label="📦 Download Receipts ZIP",
    data=zip_buf.read(),
    file_name=f"{clean_name}_receipts.zip",
    mime="application/zip",
    use_container_width=True,
)
