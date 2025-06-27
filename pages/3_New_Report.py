# File: pages/3_New_Report.py

import streamlit as st
from utils import ocr_utils, supabase_utils as su
from utils.nav_utils import PAGES_FOR_ROLES
from utils.ui_utils import hide_streamlit_pages_nav

# Page config
st.set_page_config(page_title="Create New Expense Report", layout="wide")

# Hide Streamlit’s built-in multipage nav
hide_streamlit_pages_nav()

# --- Sidebar Navigation (role-based) ---
role = st.session_state.get("role", "logged_out")
st.sidebar.header("Navigation")
for label, fname in PAGES_FOR_ROLES.get(role, PAGES_FOR_ROLES["logged_out"]):  # :contentReference[oaicite:4]{index=4}
    # Never show Add/Edit User in the sidebar
    if fname in ("7_Add_User.py", "8_Edit_User.py"):
        continue
    if st.sidebar.button(label):
        st.switch_page(f"pages/{fname}")

# --- Authentication Guard ---
if not st.session_state.get("authentication_status"):
    st.warning("Please log in to access this page.")
    st.stop()

username = st.session_state["username"]
user_id  = st.session_state["user_id"]

if not user_id:
    st.error("User profile not found in session.")
    st.stop()

# --- Main New-Report Form ---
if 'current_report_items' not in st.session_state:
    st.session_state.current_report_items = []

# Load categories
try:
    cats      = su.get_all_categories()
    cat_names = [""] + [c["name"] for c in cats]
    cat_map   = {c["name"]: c["id"] for c in cats}
except Exception as e:
    st.error(f"Could not load categories: {e}")
    cats, cat_names, cat_map = [], [""], {}

st.header("Create New Expense Report")
report_name = st.text_input("Report Name/Purpose*", placeholder="e.g., Office Supplies – June")
uploaded    = st.file_uploader("Upload Receipt (Image or PDF)", type=["png","jpg","jpeg","pdf"])

parsed, raw_text, path_db = {}, "", None
if uploaded:
    with st.spinner("Processing OCR and uploading receipt..."):
        raw_text, parsed = ocr_utils.extract_and_parse_file(uploaded)
        path_db = su.upload_receipt(uploaded, username)
        if path_db:
            st.success("Receipt uploaded successfully!")
        else:
            st.error("Failed to upload receipt.")
else:
    parsed = {"date": None, "vendor": "", "total_amount": 0.0,
              "gst_amount": 0.0, "pst_amount": 0.0, "hst_amount": 0.0,
              "line_items": []}

# Show raw OCR
with st.expander("View Raw Extracted Text"):
    st.text_area("OCR Output", raw_text, height=200)

# Edit line items if any
line_items = parsed.get("line_items", [])
if line_items:
    df = st.data_editor(
        pd.DataFrame(line_items),
        column_config={
            "category": st.column_config.SelectboxColumn("Category", options=cat_names),
            "price":    st.column_config.NumberColumn("Price", format="$%.2f")
        },
        hide_index=True,
        key="line_item_editor"
    )
    st.session_state.edited_line_items = df.to_dict("records")

with st.form("expense_item_form"):
    st.subheader("Verify Extracted Data")
    overall_cat = st.selectbox("Overall Expense Category*", options=cat_names)
    currency    = st.radio("Currency*", ["CAD","USD"], horizontal=True)
    expense_date = st.date_input("Expense Date", value=(pd.to_datetime(parsed.get("date"), errors="coerce").date() 
                                                        if parsed.get("date") else st.session_state.get("expense_date", st.session_state.current_report_items)))
    vendor       = st.text_input("Vendor Name", value=parsed.get("vendor",""))
    description  = st.text_area("Description", value=parsed.get("description",""))
    amount       = st.number_input("Amount", value=float(parsed.get("total_amount",0.0)), format="%.2f")
    submitted    = st.form_submit_button("Add Expense to Report")

    if submitted:
        item_ok = su.add_expense_item(
            report_id=None,
            expense_date=expense_date,
            vendor=vendor,
            description=description,
            amount=amount,
            currency=currency,
            category_id=cat_map.get(overall_cat),
            receipt_path=path_db,
            ocr_text=raw_text,
            gst_amount=parsed.get("gst_amount"),
            pst_amount=parsed.get("pst_amount"),
            hst_amount=parsed.get("hst_amount"),
            line_items=st.session_state.get("edited_line_items", [])
        )
        if item_ok:
            st.success("Expense added to your session report buffer.")
        else:
            st.error("Failed to save expense item.")
