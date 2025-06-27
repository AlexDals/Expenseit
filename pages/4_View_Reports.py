# File: pages/4_View_Reports.py

import streamlit as st
import pandas as pd
import io
import zipfile
import json
from utils.ui_utils import hide_streamlit_pages_nav

# *First thing* on the page:
hide_streamlit_pages_nav()

st.set_page_config(page_title="Login", layout="wide")

from utils.supabase_utils import (
    init_connection,
    get_all_reports,
    get_single_user_details,
    get_expenses_for_report,
    get_all_categories,
)

st.set_page_config(page_title="View Reports", layout="wide")
st.title("View Reports")

# ─── Init Supabase & Load Categories ───────────────────────
supabase = init_connection()
cats_df = get_all_categories()
cats = cats_df.to_dict("records") if hasattr(cats_df, "to_dict") else cats_df or []
category_map = {
    c["id"]: {"name": c["name"], "gl_account": c.get("gl_account", "")}
    for c in cats
}

# ─── Load Reports ───────────────────────────────────────────
reports_df = get_all_reports()
reports = reports_df.to_dict("records") if hasattr(reports_df, "to_dict") else reports_df or []
if not reports:
    st.info("No reports found.")
    st.stop()

# ─── Report Picker ─────────────────────────────────────────
labels = []
for rpt in reports:
    nm = rpt.get("report_name", "Untitled")
    user_obj = rpt.get("user")
    if isinstance(user_obj, dict) and user_obj.get("name"):
        filer = user_obj["name"]
    else:
        uid = rpt.get("user_id")
        filer = "Unknown"
        if uid is not None:
            usr = get_single_user_details(uid)
            filer = usr.get("name", "Unknown") if usr else "Unknown"
    labels.append(f"{nm} (filed by {filer})")

sel = st.selectbox("Select a report", labels, index=0)
report = reports[labels.index(sel)]

# ─── Fetch Expenses & Build Summary DataFrame ──────────────
items = get_expenses_for_report(report["id"])
items_df = pd.DataFrame(items)

if not items_df.empty:
    # Rename core columns
    df = items_df.rename(columns={
        "expense_date": "Date",
        "date":         "Date",
        "vendor":       "Vendor",
        "description":  "Description",
        "amount":       "Amount",
        "gst_amount":   "GST",
        "pst_amount":   "PST",
        "hst_amount":   "HST",
    })
    # Map each expense’s overall category
    df["Category"] = items_df["category_id"].map(
        lambda cid: category_map.get(cid, {}).get("name", "")
    )
    df["GL Account Number"] = items_df["category_id"].map(
        lambda cid: category_map.get(cid, {}).get("gl_account", "")
    )
    summary_cols = ["Date", "Vendor", "Description", "Amount", "GST", "PST", "HST", "Category", "GL Account Number"]
    summary_df = df[summary_cols]
    st.dataframe(summary_df)
else:
    st.write("No expense items found for this report.")

# ─── Line Items Breakdown ──────────────────────────────────
st.markdown("### Line Items Breakdown")
for _, row in items_df.iterrows():
    pd_date   = row.get("date") or row.get("expense_date")
    pd_vendor = row.get("vendor")
    with st.expander(f"{pd_date} – {pd_vendor}"):
        raw_li = row.get("line_items") or []
        # Parse JSON string if needed
        if isinstance(raw_li, str):
            try:
                raw_li = json.loads(raw_li)
            except Exception:
                raw_li = []
        if not isinstance(raw_li, list):
            st.write("No line items")
            continue

        # Build DataFrame
        try:
            li_df = pd.DataFrame(raw_li)
        except Exception:
            st.error("Unable to display line items")
            continue

        # Add GL Account for each line item’s category
        li_df["Category"] = li_df["category_id"].map(
            lambda cid: category_map.get(cid, {}).get("name", "")
        )
        li_df["GL Account Number"] = li_df["category_id"].map(
            lambda cid: category_map.get(cid, {}).get("gl_account", "")
        )

        # Rename columns to user-friendly names
        rename_map = {
            "description":    "Line Description",
            "price":          "Line Price",
            "Category":       "Category",
            "category_id":    "Category ID",
            "GL Account Number": "GL Account Number",
        }
        to_show = []
        for orig, new in rename_map.items():
            if orig in li_df.columns:
                li_df = li_df.rename(columns={orig: new})
                to_show.append(new)

        st.dataframe(li_df[to_show])

# ─── Base filename for downloads ───────────────────────────
base = report.get("report_name", "report").replace(" ", "_")

# ─── Export as Excel ───────────────────────────────────────
if not items_df.empty:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        # Summary sheet
        summary_df.to_excel(writer, index=False, sheet_name="Summary")
        # Line Items sheet
        detail_rows = []
        for _, row in items_df.iterrows():
            p_date   = row.get("date") or row.get("expense_date")
            p_vendor = row.get("vendor")
            p_amt    = row.get("amount")
            raw_li   = row.get("line_items") or []
            if isinstance(raw_li, str):
                try:
                    raw_li = json.loads(raw_li)
                except Exception:
                    raw_li = []
            if isinstance(raw_li, list):
                for li in raw_li:
                    if not isinstance(li, dict):
                        continue
                    cid = li.get("category_id")
                    detail_rows.append({
                        "Parent Date":        p_date,
                        "Parent Vendor":      p_vendor,
                        "Parent Amount":      p_amt,
                        "Line Description":   li.get("description"),
                        "Line Price":         li.get("price"),
                        "Category":           category_map.get(cid, {}).get("name", ""),
                        "Category ID":        cid,
                        "GL Account Number":  category_map.get(cid, {}).get("gl_account", ""),
                    })
        if detail_rows:
            pd.DataFrame(detail_rows).to_excel(
                writer, index=False, sheet_name="Line Items"
            )
    buf.seek(0)
    st.download_button(
        label="📊 Export as Excel",
        data=buf.read(),
        file_name=f"{base}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

# ─── Download Receipts ZIP ─────────────────────────────────
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
                fn = path.split("/")[-1]
                zf.writestr(fn, file_bytes)
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
