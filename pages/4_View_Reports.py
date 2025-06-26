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

# — Initialize Supabase client
supabase = init_connection()

# — Load list of reports
reports_df = get_all_reports()
if hasattr(reports_df, "to_dict"):
    reports = reports_df.to_dict("records")
else:
    reports = reports_df or []

if not reports:
    st.info("No reports found.")
    st.stop()

# — Build dropdown with “filed by” context
labels = []
for rpt in reports:
    rpt_name = rpt.get("report_name", "Untitled")
    user_obj = rpt.get("user")
    if isinstance(user_obj, dict) and user_obj.get("name"):
        filer = user_obj["name"]
    else:
        uid = rpt.get("user_id")
        filer = "Unknown"
        if uid is not None:
            usr = get_single_user_details(uid)
            filer = usr.get("name", "Unknown") if usr else "Unknown"
    labels.append(f"{rpt_name} (filed by {filer})")

selected = st.selectbox("Select a report", labels, index=0)
report = reports[labels.index(selected)]

# — Fetch and display only the four key columns
items_df = get_expenses_for_report(report["id"])
if not items_df.empty:
    # Rename possible date field, then slice down to the four columns
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

# — Generate XML and force it to bytes for the download button
report_series = pd.Series(report)
# Extract the filer’s name from the label
submitter_name = selected.split("filed by ")[1].rstrip(")")
xml_data = generate_report_xml(report_series, items_df, submitter_name)
xml_bytes = xml_data.encode("utf-8") if isinstance(xml_data, str) else xml_data
clean_name = report.get("report_name", "report").replace(" ", "_")

st.download_button(
    label="💿 Download as XML",
    data=xml_bytes,
    file_name=f"{clean_name}.xml",
    mime="application/xml",
    use_container_width=True,
)

# — Bundle all receipt files into an in-memory ZIP and offer it
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
            # skip files we can’t fetch
            pass

zip_buffer.seek(0)
st.download_button(
    label="📦 Download Receipts ZIP",
    data=zip_buffer.read(),
    file_name=f"{clean_name}_receipts.zip",
    mime="application/zip",
    use_container_width=True,
)
