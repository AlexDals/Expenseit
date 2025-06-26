# File: pages/4_View_Reports.py

import streamlit as st
import pandas as pd
import io
import zipfile
from utils.supabase_utils import (
    init_connection,
    get_all_reports,
    get_expenses_for_report,
    generate_report_xml,
)

st.set_page_config(page_title="View Reports", layout="wide")
st.title("View Reports")

# 1) Supabase client
supabase = init_connection()

# 2) Load all reports
reports_df: pd.DataFrame = get_all_reports()
if reports_df.empty:
    st.info("No reports found.")
    st.stop()

# 3) Let the user pick one
report_names = reports_df["report_name"].tolist()
selected_name = st.selectbox("Select a report", report_names)
selected_idx = report_names.index(selected_name)
selected_report = reports_df.iloc[selected_idx]  # pd.Series

# 4) Fetch expense items for that report
items_df: pd.DataFrame = get_expenses_for_report(selected_report["id"])
st.markdown("### Report Items")
st.dataframe(items_df)

# 5) Build the XML
#    generate_report_xml(report_series, items_df, submitter_name)
#    We pull the submitter’s name from the nested 'user' dict if present
user_field = selected_report.get("user")
submitter_name = user_field.get("name") if isinstance(user_field, dict) else ""
xml_obj = generate_report_xml(selected_report, items_df, submitter_name)

# Ensure we have bytes for download_button
xml_bytes = xml_obj.encode("utf-8") if isinstance(xml_obj, str) else xml_obj
clean_name = selected_name.replace(" ", "_")

# 6) Download as XML
st.download_button(
    label="💿 Download as XML",
    data=xml_bytes,
    file_name=f"{clean_name}.xml",
    mime="application/xml",
    use_container_width=True,
)

# 7) Build a ZIP of all receipt files
zip_buffer = io.BytesIO()
with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
    for _, row in items_df.iterrows():
        path = row.get("receipt_path")
        if not path:
            continue
        try:
            resp = supabase.storage.from_("receipts").download(path)
            # supabase-py v2 returns {'data': bytes, 'error': None}, v1 returns raw bytes
            file_bytes = resp.get("data") if isinstance(resp, dict) else resp
            if file_bytes:
                filename = path.split("/")[-1]
                zf.writestr(filename, file_bytes)
        except Exception as e:
            st.warning(f"Could not include {path}: {e}")

zip_buffer.seek(0)

# 8) Download ZIP
st.download_button(
    label="📦 Download Receipts ZIP",
    data=zip_buffer.read(),
    file_name=f"{clean_name}_receipts.zip",
    mime="application/zip",
    use_container_width=True,
)
