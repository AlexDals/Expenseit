# File: pages/4_View_Reports.py

import streamlit as st
from utils.ui_utils import hide_streamlit_pages_nav

# *First thing* on the page:
hide_streamlit_pages_nav()

import pandas as pd
import io
import zipfile
import json
from utils import supabase_utils as su

st.set_page_config(layout="wide", page_title="View Reports")

# --- Authentication Guard ---
if not st.session_state.get("authentication_status"):
    st.warning("Please log in to access this page.")
    st.stop()

# Load all reports
reports = su.get_all_reports()
if hasattr(reports, "to_dict"):
    reports = reports.to_dict("records")
else:
    reports = reports or []

if not reports:
    st.info("No reports found.")
    st.stop()

# Dropdown with “filed by”
labels = []
for rpt in reports:
    name = rpt.get("report_name", "Untitled")
    user_obj = rpt.get("user") or {}
    filer = user_obj.get("name") or su.get_single_user_details(rpt.get("user_id", 0)).get("name", "Unknown")
    labels.append(f"{name} (filed by {filer})")

selected = st.selectbox("Select a report", labels, index=0)
report   = reports[labels.index(selected)]

# Fetch and display core columns
items = su.get_expenses_for_report(report["id"])
df    = pd.DataFrame(items)
if not df.empty:
    df0 = df.rename(columns={
        "expense_date": "Date", "vendor": "Vendor", "description": "Description",
        "amount": "Amount", "gst_amount": "GST", "pst_amount": "PST", "hst_amount": "HST"
    })
    st.dataframe(df0[["Date", "Vendor", "Description", "Amount", "GST", "PST", "HST"]])
else:
    st.write("No expense items found for this report.")

# Line Items Breakdown
st.markdown("### Line Items Breakdown")
for _, row in df.iterrows():
    parent_date   = row.get("date") or row.get("expense_date")
    parent_vendor = row.get("vendor")
    with st.expander(f"{parent_date} – {parent_vendor}"):
        raw_li = row.get("line_items") or []
        if isinstance(raw_li, str):
            try:
                raw_li = json.loads(raw_li)
            except Exception:
                st.error("Could not parse line_items JSON")
                raw_li = []
        if not isinstance(raw_li, list):
            st.write("No line items")
            continue
        try:
            li_df = pd.DataFrame(raw_li)
            # Map category and GL account
            cats = su.get_all_categories()
            cmap = {c["id"]: {"name": c["name"], "gl": c.get("gl_account", "")} for c in cats}
            li_df["Category"]     = li_df["category_id"].map(lambda i: cmap.get(i, {}).get("name", ""))
            li_df["GL Account #"] = li_df["category_id"].map(lambda i: cmap.get(i, {}).get("gl", ""))
            li_df = li_df.rename(columns={"description": "Line Description", "price": "Line Price"})
            st.dataframe(li_df[["Line Description", "Line Price", "Category", "GL Account #"]])
        except Exception as e:
            st.error(f"Unable to display line items: {e}")

# Base filename
base = report.get("report_name", "report").replace(" ", "_")

# Export as Excel (Summary + Line Items)
if not df.empty:
    excel_buf = io.BytesIO()
    with pd.ExcelWriter(excel_buf, engine="openpyxl") as writer:
        # Summary sheet
        df0[["Date", "Vendor", "Description", "Amount", "GST", "PST", "HST"]].to_excel(
            writer, sheet_name="Summary", index=False
        )
        # Line Items sheet
        detail = []
        for _, row in df.iterrows():
            pdate = row.get("date") or row.get("expense_date")
            pvend = row.get("vendor")
            pamt  = row.get("amount")
            raw_li = row.get("line_items") or []
            if isinstance(raw_li, str):
                try:
                    raw_li = json.loads(raw_li)
                except Exception:
                    raw_li = []
            for itm in raw_li:
                if not isinstance(itm, dict):
                    continue
                cid = itm.get("category_id")
                detail.append({
                    "Parent Date":        pdate,
                    "Parent Vendor":      pvend,
                    "Parent Amount":      pamt,
                    "Line Description":   itm.get("description"),
                    "Line Price":         itm.get("price"),
                    "Category":           itm.get("category_name") or itm.get("category", ""),
                    "Category ID":        cid,
                    "GL Account #":       next((c["gl_account"] for c in su.get_all_categories() if c["id"] == cid), "")
                })
        if detail:
            pd.DataFrame(detail).to_excel(writer, sheet_name="Line Items", index=False)
    excel_buf.seek(0)
    st.download_button(
        label="📊 Export as Excel",
        data=excel_buf.read(),
        file_name=f"{base}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

# Download receipts ZIP
zip_buf = io.BytesIO()
with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
    for _, row in df.iterrows():  
        path = row.get("receipt_path")
        if not path:
            continue
        try:
            resp = su.init_connection().storage.from_("receipts").download(path)
            data = resp.get("data") if isinstance(resp, dict) else resp
            if data:
                zf.writestr(path.split("/")[-1], data)
        except Exception:
            pass
zip_buf.seek(0)
st.download_button(
    label="📦 Download Receipts ZIP",
    data=zip_buf.read(),
    file_name=f"{base}_receipts.zip",
    mime="application/zip",
    use_container_width=True,
)
