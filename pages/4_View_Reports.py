# File: pages/4_View_Reports.py

import streamlit as st
import pandas as pd
import io
import zipfile
from utils.supabase_utils import (
    init_connection,
    get_all_reports,
    get_report_items,
    generate_report_xml,  # or however you build your XML
)

st.set_page_config(page_title="View Reports", layout="wide")
st.title("View Reports")

# — Initialize Supabase client
supabase = init_connection()

# — Load list of reports
reports = get_all_reports()  # returns List[Dict] with at least 'id' and 'report_name'
if not reports:
    st.info("No reports found.")
    st.stop()

# — Let user pick one
report_df = pd.DataFrame(reports)
report_names = report_df["report_name"].tolist()
selected_name = st.selectbox("Select a report", report_names, index=0)
selected_report = next(r for r in reports if r["report_name"] == selected_name)

# — Show the items in the report
items = get_report_items(selected_report["id"])  # returns List[Dict]
st.markdown("### Report Items")
st.dataframe(pd.DataFrame(items))

# — Generate XML for this report
xml_data = generate_report_xml(selected_report, items)
# Ensure xml_data is bytes
if isinstance(xml_data, str):
    xml_bytes = xml_data.encode("utf-8")
else:
    xml_bytes = xml_data

clean_name = selected_name.replace(" ", "_")

# — Download XML
st.download_button(
    label="💿 Download as XML",
    data=xml_bytes,
    file_name=f"{clean_name}.xml",
    mime="application/xml",
    use_container_width=True,
)

# — Create in-memory ZIP of all receipt files
zip_buffer = io.BytesIO()
with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
    for item in items:
        path = item.get("receipt_path")
        if not path:
            continue
        try:
            # Download from Supabase storage
            resp = supabase.storage.from_("receipts").download(path)
            # Handle v1 (Response-like) and v2 (dict) clients
            if isinstance(resp, dict):
                file_bytes = resp.get("data")
            else:
                file_bytes = resp
            if not file_bytes:
                continue
            # Use only the basename for the file inside the zip
            filename = path.split("/")[-1]
            zf.writestr(filename, file_bytes)
        except Exception as e:
            st.warning(f"Could not include {path} in ZIP: {e}")

zip_buffer.seek(0)
# — Download ZIP
st.download_button(
    label="📦 Download Receipts ZIP",
    data=zip_buffer.read(),
    file_name=f"{clean_name}_receipts.zip",
    mime="application/zip",
    use_container_width=True,
)
