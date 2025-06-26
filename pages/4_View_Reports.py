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

# Load list of reports (could be a DataFrame or list of dicts)
reports = su.get_all_reports()

# Normalize to a list of dicts
if hasattr(reports, "to_dict"):
    reports_list = reports.to_dict("records")
else:
    reports_list = reports or []

# Guard against empty
if not reports_list:
    st.info("No reports found.")
    st.stop()

# Build dropdown with “filed by” context
options = [
    f"{r['report_name']} (filed by {r.get('username', 'Unknown')})"
    for r in reports_list
]
selected = st.selectbox("Select a report", options, index=0)
report = reports_list[options.index(selected)]

# Fetch and display only the relevant columns
items = su.get_report_items(report["id"])  # returns list of dicts
items_df = pd.DataFrame(items)
if not items_df.empty:
    display_df = items_df[["date", "vendor", "description", "amount"]]
    st.dataframe(display_df)
else:
    st.write("No expense items found for this report.")

# Generate XML for download
xml_data = su.generate_report_xml(report, items)
xml_bytes = xml_data.encode("utf-8") if isinstance(xml_data, str) else xml_data
clean_name = report["report_name"].replace(" ", "_")

# Download XML
st.download_button(
    label="💿 Download as XML",
    data=xml_bytes,
    file_name=f"{clean_name}.xml",
    mime="application/xml",
    use_container_width=True,
)

# Build ZIP of receipts
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
            pass

zip_buf.seek(0)
st.download_button(
    label="📦 Download Receipts ZIP",
    data=zip_buf.read(),
    file_name=f"{clean_name}_receipts.zip",
    mime="application/zip",
    use_container_width=True,
)
