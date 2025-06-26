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
    get_single_user_details,
)

st.set_page_config(page_title="View Reports", layout="wide")
st.title("View Reports")

# 1) Initialize Supabase
supabase = init_connection()

# 2) Load all reports
reports_df = get_all_reports()
if hasattr(reports_df, "to_dict"):
    reports = reports_df.to_dict("records")
else:
    reports = reports_df or []

if not reports:
    st.info("No reports found.")
    st.stop()

# 3) Build dropdown with “filed by” using the nested user object or falling back to a lookup
labels = []
for r in reports:
    rpt_name = r.get("report_name", "Untitled")
    # Supabase returns a “user” field because of the select("*, user:users!left(name)")
    user_obj = r.get("user")
    if isinstance(user_obj, dict) and user_obj.get("name"):
        filer = user_obj["name"]
    else:
        # fallback: if there’s a user_id, fetch it
        uid = r.get("user_id")
        filer = "Unknown"
        if uid is not None:
            user = get_single_user_details(uid)
            filer = user.get("name", "Unknown") if user else "Unknown"
    labels.append(f"{rpt_name} (filed by {filer})")

selected_label = st.selectbox("Select a report", labels, index=0)
selected_idx = labels.index(selected_label)
report = reports[selected_idx]

# 4) Fetch and display only the key columns from that report’s expenses
items_df = get_expenses_for_report(report["id"])
if not items_df.empty:
    # rename expense_date → Date for clarity, then select columns
    disp = (
        items_df
        .rename(columns={"expense_date": "Date", "vendor": "Vendor", "description": "Description", "amount": "Amount"})
        [["Date", "Vendor", "Description", "Amount"]]
    )
    st.dataframe(disp)
else:
    st.write("No expense items found for this report.")

# 5) Generate and download the XML
xml_data = generate_report_xml(pd.Series(report), items_df, None)
xml_bytes = xml_data.encode("utf-8") if isinstance(xml_data, str) else xml_data
base = report.get("report_name", "report").replace(" ", "_")
st.download_button(
    label="💿 Download as XML",
    data=xml_bytes,
    file_name=f"{base}.xml",
    mime="application/xml",
    use_container_width=True,
)

# 6) Bundle all receipt files into a ZIP and offer it for download
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
                name = path.split("/")[-1]
                zf.writestr(name, file_bytes)
        except Exception:
            # skip missing or errored files
            pass

zip_buffer.seek(0)
st.download_button(
    label="📦 Download Receipts ZIP",
    data=zip_buffer.read(),
    file_name=f"{base}_receipts.zip",
    mime="application/zip",
    use_container_width=True,
)
