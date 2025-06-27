# File: pages/4_View_Reports.py

import streamlit as st
import pandas as pd
import zipfile, io, json
from utils import supabase_utils as su
from utils.nav_utils import PAGES_FOR_ROLES
from utils.ui_utils import hide_streamlit_pages_nav

# Page config
st.set_page_config(page_title="View Reports", layout="wide")

# Hide Streamlit’s built-in multipage nav
hide_streamlit_pages_nav()

# --- Sidebar Navigation (role-based) ---
role = st.session_state.get("role", "logged_out")
st.sidebar.header("Navigation")
for label, fname in PAGES_FOR_ROLES.get(role, PAGES_FOR_ROLES["logged_out"]):  # :contentReference[oaicite:5]{index=5}
    if fname in ("7_Add_User.py", "8_Edit_User.py"):
        continue
    if st.sidebar.button(label):
        st.switch_page(f"pages/{fname}")

# --- Authentication Guard ---
if not st.session_state.get("authentication_status"):
    st.warning("Please log in to access this page.")
    st.stop()

# --- Load and select a report ---
reports = su.get_all_reports()
records = reports.to_dict("records") if hasattr(reports, "to_dict") else reports or []
if not records:
    st.info("No reports found.")
    st.stop()

labels = [
    f"{r['report_name']} (by {r.get('user',{}).get('name', 'Unknown')})"
    for r in records
]
choice = st.selectbox("Select a report", labels)
report = records[labels.index(choice)]

# --- Display summary table ---
df = su.get_expenses_for_report(report["id"])
if not df.empty:
    st.dataframe(df[["expense_date","vendor","description","amount","gst_amount","pst_amount","hst_amount"]]
                 .rename(columns={
                     "expense_date":"Date","vendor":"Vendor","description":"Description",
                     "amount":"Amount","gst_amount":"GST","pst_amount":"PST","hst_amount":"HST"
                 }))
else:
    st.write("No expense items found for this report.")

# --- Line items breakdown ---
st.markdown("### Line Items Breakdown")
for _, row in df.iterrows():
    date = row["expense_date"]
    vendor = row["vendor"]
    with st.expander(f"{date} – {vendor}"):
        raw_li = row.get("line_items", [])
        if isinstance(raw_li, str):
            try:
                raw_li = json.loads(raw_li)
            except:
                st.error("Could not parse line_items JSON")
                continue
        if not raw_li:
            st.write("No line items")
            continue

        li_df = pd.DataFrame(raw_li)
        cats = su.get_all_categories()
        cmap = {c["id"]:{"name":c["name"],"gl":c.get("gl_account","")} for c in cats}
        li_df["Category"]     = li_df["category_id"].map(lambda i: cmap.get(i,{}).get("name",""))
        li_df["GL Account #"] = li_df["category_id"].map(lambda i: cmap.get(i,{}).get("gl",""))
        st.dataframe(li_df.rename(columns={"description":"Line Description","price":"Line Price"})[
            ["Line Description","Line Price","Category","GL Account #"]
        ])

# --- Export options ---
base = report.get("report_name","report").replace(" ","_")
if st.button("Download Excel"):
    to_excel = io.BytesIO()
    with pd.ExcelWriter(to_excel, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Expenses")
        pd.DataFrame(li_df).to_excel(writer, index=False, sheet_name="LineItems")
    to_excel.seek(0)
    st.download_button("Download .xlsx", data=to_excel, file_name=f"{base}.xlsx")
