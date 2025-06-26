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

# 1) Initialize Supabase client
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

# 3) Build dropdown with “filed by” labels
labels = []
submitter_map = {}
for rpt in reports:
    name = rpt.get("report_name", "Untitled")
    # Prefer the nested user dict if present
    user_obj = rpt.get("user")
    if isinstance(user_obj, dict) and user_obj.get("name"):
        filer = user_obj["name"]
    else:
        # Fallback: look up by user_id
        uid = rpt.get("user_id")
        if uid is not None:
            usr = get_single_user_details(uid)
            filer = usr.get("name", "Unknown") if usr else "Unknown"
        else:
            filer = "Unknown"
    labels.append(f"{name} (filed by {filer})")
    submitter_map[rpt["id"]] = filer

selected = st.selectbox("Select a report", labels, index=0)
report = reports[labels.index(selected)]
submitter_name = submitter_map.get(report["id"], "")

# 4) Fetch expense items and display only the core columns
items_df = get_expenses_for_report(report["id"])
if not items_df.empty:
    cols = list(items_df.columns)
    # Heuristically pick columns
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

# 5) Generate XML (pass all three args, per the supabase_utils signature)
#    Wrap report dict in a Series and supply submitter_name
xml_bytes = None
try:
    report_series = pd.Series(report)
    xml_data = generate_report_xml(report_series, items_df, submitter_name)
    xml_bytes = xml_data.encode("utf-8") if isinstance(xml_data, str) else xml_data
except Exception as e:
    st.error(f"Error generating XML: {e}")

if xml_bytes:
    clean_name = report.get("report_name", "report").replace(" ", "_")
    st.download_button(
        label="💿 Download as XML",
        data=xml_bytes,
        file_name=f"{clean_name}.xml",
        mime="application/xml",
        use_container_width=True,
    )

# 6) Bundle receipts into a ZIP for download
zip_buf = io.BytesIO()
with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
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
zip_buf.seek(0)

st.download_button(
    label="📦 Download Receipts ZIP",
    data=zip_buf.read(),
    file_name=f"{clean_name}_receipts.zip",
    mime="application/zip",
    use_container_width=True,
)
