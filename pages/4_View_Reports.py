# File: pages/4_View_Reports.py

import streamlit as st
import pandas as pd
import io
import zipfile
from utils import supabase_utils as su

st.set_page_config(page_title="View Reports", layout="wide")
st.title("View Reports")

# — Initialize Supabase client
supabase = su.init_connection()

# — Load list of reports
reports = su.get_all_reports()  # returns List[Dict] with at least 'id', 'report_name', 'username'
if not reports:
    st.info("No reports found.")
    st.stop()

# — Build dropdown with “filed by” context
options = [
    f"{r['report_name']} (filed by {r.get('username','Unknown')})"
    for r in reports
]
selected = st.selectbox("Select a report", options, index=0)
report = reports[options.index(selected)]

# — Show just the relevant columns in the grid
items = su.get_report_items(report["id"])  # returns List[Dict]
df_items = pd.DataFrame(items)
if not df_items.empty:
    display_df = df_items[["date", "vendor", "description", "amount"]]
    st.dataframe(display_df)
else:
    st.write("No expense items found for this report.")

# — Generate XML
xml_data = su.generate_report_xml(report, items)
# Convert to bytes if it’s a str
xml_bytes = xml_data.encode("utf-8") if isinstance(xml_data, str) else xml_data

clean_name = report["report_name"].replace(" ", "_")

# — Download XML as bytes
st.download_button(
    label="💿 Download as XML",
    data=xml_bytes,
    file_name=f"{clean_name}.xml",
    mime="application/xml",
    use_container_width=True,
)

# — Build a ZIP of all receipt files
zip_buf = io.BytesIO()
with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
    for item in items:
        path = item.get("receipt_path")
        if not path:
            continue
        try:
            resp = supabase.storage.from_("receipts").download(path)
            # Supabase-py v2 returns dict, v1 returns raw bytes
            file_bytes = resp.get("data") if isinstance(resp, dict) else resp
            if file_bytes:
                fname = path.split("/")[-1]
                zf.writestr(fname, file_bytes)
        except Exception:
            # Skip files we can’t fetch
            pass

zip_buf.seek(0)
st.download_button(
    label="📦 Download Receipts ZIP",
    data=zip_buf.read(),
    file_name=f"{clean_name}_receipts.zip",
    mime="application/zip",
    use_container_width=True,
)
