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
)

st.set_page_config(page_title="View Reports", layout="wide")
st.title("View Reports")

# ─── Init Supabase ─────────────────────────────────────────
supabase = init_connection()

# ─── Load Reports ──────────────────────────────────────────
reports_df = get_all_reports()
if hasattr(reports_df, "to_dict"):
    reports = reports_df.to_dict("records")
else:
    reports = reports_df or []

if not reports:
    st.info("No reports found.")
    st.stop()

# ─── Report Picker ─────────────────────────────────────────
labels = []
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

selected = st.selectbox("Select a report", labels, index=0)
report = reports[labels.index(selected)]

# ─── Fetch & Display Core Columns ─────────────────────────
items_df = get_expenses_for_report(report["id"])
if not items_df.empty:
    df = items_df.rename(columns={
        "expense_date":   "Date",
        "vendor":         "Vendor",
        "description":    "Description",
        "amount":         "Amount",
        "gst_amount":     "GST",
        "pst_amount":     "PST",
        "hst_amount":     "HST",
    })
    display_df = df[["Date", "Vendor", "Description", "Amount", "GST", "PST", "HST"]]
    st.dataframe(display_df)
else:
    st.write("No expense items found for this report.")

# ─── Base Filename ─────────────────────────────────────────
base_name = report.get("report_name", "report").replace(" ", "_")

# ─── Export as Excel ───────────────────────────────────────
if not items_df.empty:
    excel_buffer = io.BytesIO()
    with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
        # Summary sheet
        display_df.to_excel(writer, index=False, sheet_name="Summary")

        # Line Items sheet
        detail_rows = []
        for _, row in items_df.iterrows():
            parent_date   = row.get("date") or row.get("expense_date")
            parent_vendor = row.get("vendor")
            for li in row.get("line_items", []):
                detail_rows.append({
                    "Parent Date":   parent_date,
                    "Parent Vendor": parent_vendor,
                    "Description":   li.get("description"),
                    "Price":         li.get("price"),
                    "Category":      li.get("category_name"),
                    "Category ID":   li.get("category_id"),
                })
        if detail_rows:
            pd.DataFrame(detail_rows).to_excel(
                writer, index=False, sheet_name="Line Items"
            )

    excel_buffer.seek(0)
    st.download_button(
        label="📊 Export as Excel",
        data=excel_buffer.read(),
        file_name=f"{base_name}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

# ─── Download Receipts ZIP ─────────────────────────────────  
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
