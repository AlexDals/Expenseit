import streamlit as st
from utils.nav_utils import filter_pages_by_role
filter_pages_by_role()

import pandas as pd
import io
import zipfile
import json
from utils import supabase_utils as su

st.set_page_config(layout="wide", page_title="View Reports")

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

# Dropdown
labels = []
for rpt in reports:
    nm = rpt.get("report_name", "Untitled")
    user = rpt.get("user") or {}
    filer = user.get("name") or su.get_single_user_details(rpt.get("user_id", 0)).get("name", "Unknown")
    labels.append(f"{nm} (filed by {filer})")

sel = st.selectbox("Select a report", labels)
report = reports[labels.index(sel)]

# Fetch items
items = su.get_expenses_for_report(report["id"])
df = pd.DataFrame(items)
if not df.empty:
    df0 = df.rename(columns={
        "expense_date": "Date", "vendor": "Vendor", "description": "Description",
        "amount": "Amount", "gst_amount":"GST", "pst_amount":"PST","hst_amount":"HST"
    })
    st.dataframe(df0[["Date","Vendor","Description","Amount","GST","PST","HST"]])
else:
    st.write("No items.")

# Line items breakdown
st.markdown("### Line Items Breakdown")
for _, row in df.iterrows():
    pdate = row.get("date") or row.get("expense_date")
    pvend = row.get("vendor")
    with st.expander(f"{pdate} — {pvend}"):
        li = row.get("line_items") or []
        if isinstance(li, str):
            try: li = json.loads(li)
            except: li = []
        if not isinstance(li, list):
            st.write("No line items.")
            continue
        try:
            lidf = pd.DataFrame(li)
            # map category & GL account
            cats = su.get_all_categories()
            cmap = {c["id"]:{ "name":c["name"], "gl":c.get("gl_account","")} for c in cats}
            lidf["Category"] = lidf["category_id"].map(lambda i: cmap.get(i,{}).get("name",""))
            lidf["GL Account"] = lidf["category_id"].map(lambda i: cmap.get(i,{}).get("gl",""))
            lidf = lidf.rename(columns={"description":"Line Description","price":"Line Price"})
            cols = ["Line Description","Line Price","Category","GL Account"]
            st.dataframe(lidf[cols])
        except Exception as e:
            st.error(f"Unable to display line items: {e}")

# Base filename
base = report.get("report_name","report").replace(" ","_")

# Export as Excel
if not df.empty:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        # summary
        df0[["Date","Vendor","Description","Amount","GST","PST","HST"]].to_excel(writer, sheet_name="Summary", index=False)
        # line items sheet
        detail = []
        for _, row in df.iterrows():
            pdate = row.get("date") or row.get("expense_date")
            pvend = row.get("vendor")
            pamt  = row.get("amount")
            li = row.get("line_items") or []
            if isinstance(li, str):
                try: li = json.loads(li)
                except: li = []
            for itm in li:
                if not isinstance(itm, dict): continue
                cid = itm.get("category_id")
                detail.append({
                    "Parent Date": pdate, "Parent Vendor": pvend, "Parent Amount": pamt,
                    "Line Description": itm.get("description"), "Line Price": itm.get("price"),
                    "Category": itm.get("category_name") or itm.get("category",""),
                    "Category ID": cid, "GL Account": next((c["gl_account"] for c in su.get_all_categories() if c["id"]==cid), "")
                })
        if detail:
            pd.DataFrame(detail).to_excel(writer, sheet_name="Line Items", index=False)
    buf.seek(0)
    st.download_button(
        "📊 Export as Excel",
        data=buf.read(),
        file_name=f"{base}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# Download receipts ZIP
zipbuf = io.BytesIO()
with zipfile.ZipFile(zipbuf, "w", zipfile.ZIP_DEFLATED) as zf:
    for _, row in df.iterrows():
        path = row.get("receipt_path")
        if not path: continue
        try:
            resp = su.init_connection().storage.from_("receipts").download(path)
            data = resp.get("data") if isinstance(resp, dict) else resp
            if data:
                zf.writestr(path.split("/")[-1], data)
        except:
            pass
zipbuf.seek(0)
st.download_button(
    "📦 Download Receipts ZIP",
    data=zipbuf.read(),
    file_name=f"{base}_receipts.zip",
    mime="application/zip"
)
