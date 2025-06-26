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

# ─── Initialize Supabase ─────────────────────────────────
supabase = init_connection()

# ─── Load all reports ────────────────────────────────────
reports_df = get_all_reports()
if hasattr(reports_df, "to_dict"):
    reports = reports_df.to_dict("records")
else:
    reports = reports_df or []

if not reports:
    st.info("No reports found.")
    st.stop()

# ─── Build dropdown with “filed by” labels ───────────────
labels = []
for rpt in reports:
    rpt_name = rpt.get("report_name", "Untitled")
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
    labels.append(f"{rpt_name} (filed by {filer})")

selected = st.selectbox("Select a report", labels, index=0)
report = reports[labels.index(selected)]

# ─── Fetch & display core expense columns ───────────────
items_df = get_expenses_for_report(report["id"])
if not items_df.empty:
    df = items_df.rename(columns={
        "expense_date": "Date",
        "vendor":       "Vendor",
        "description":  "Description",
        "amount":       "Amount",
        "gst_amount":   "GST",
        "pst_amount":   "PST",
        "hst_amount":   "HST",
    })
    display_df = df[["Date", "Vendor", "Description", "Amount", "GST", "PST", "HST"]]
    st.dataframe(display_df)
else:
    st.write("No expense items found for this report.")

# ─── Prepare base filename for downloads ─────────────────
base_name = report.get("report_name", "report").replace(" ", "_")

# ─── Export as Excel (Summary + Line Items) ─────────────
if not items_df.empty:
    excel_buffer = io.BytesIO()
    with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
        # 1) Summary sheet
        display_df.to_excel(writer, index=False, sheet_name="Summary")

        # 2) Line Items sheet: flatten every `line_items`
        detail_rows = []
        for _, row in items_df.iterrows():
            parent_date   = row.get("date") or row.get("expense_date")
            parent_vendor = row.get("vendor")
            parent_amt    = row.get("amount")
            parent_desc   = row.get("description")
            for li in row.get("line_items") or []:
                if not isinstance(li, dict):
                    continue
                detail_rows.append({
                    "Parent Date":        parent_date,
                    "Parent Vendor":      parent_vendor,
                    "Parent Amount":      parent_amt,
                    "Parent Description": parent_desc,
                    "Line Description":   li.get("description"),
                    "Line Price":         li.get("price"),
                    "Category":           li.get("category_name") or li.get("category"),
                    "Category ID":        li.get("category_id"),
                })
        if detail_rows:
            pd.DataFrame(detail_rows).to_excel(
                writer,
                index=False,
                sheet_name="Line Items"
            )

    excel_buffer.seek(0)
    st.download_button(
        label="📊 Export as Excel",
        data=excel_buffer.read(),
        file_name=f"{base_name}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

# ─── Bundle receipts into ZIP ───────────────────────────
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
