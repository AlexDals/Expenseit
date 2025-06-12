import streamlit as st
from supabase import create_client, Client
import pandas as pd
from datetime import datetime
import os
import json
import xml.etree.ElementTree as ET
from xml.dom import minidom

@st.cache_resource
def init_connection() -> Client:
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key)
    except KeyError:
        st.error("Supabase credentials not found. Please add your secrets in the Streamlit Cloud dashboard.")
        st.stop()

# --- NEW FUNCTION: XML EXPORTER ---
def generate_report_xml(report_id: str, report_data: pd.Series, expenses_data: pd.DataFrame, submitter_name: str) -> str:
    """
    Generates an XML string for a given report in the specified format.
    """
    # Helper to create sub-elements
    def create_sub_element(parent, tag, text):
        element = ET.SubElement(parent, tag)
        element.text = str(text) if text is not None else ""
        return element

    # Create the root element
    record = ET.Element("Record")

    # Create Header
    header = ET.SubElement(record, "Header", {"Table": "PurcHdr", "TableType": "1"})
    rows_header = ET.SubElement(header, "Rows")
    row_header = ET.SubElement(rows_header, "Row")
    
    # Get the first expense for vendor info
    first_expense = expenses_data.iloc[0] if not expenses_data.empty else {}

    # Populate Header Row
    create_sub_element(row_header, "ExSuppId", first_expense.get('vendor', 'N/A')).set("MemberName", "SuppId")
    create_sub_element(row_header, "PurcDate", report_data.get('submission_date', '')[:10])
    create_sub_element(row_header, "DocNo", report_data.get('report_name', ''))
    create_sub_element(row_header, "Remarks", report_data.get('report_name', '')) # Per your request
    create_sub_element(row_header, "PurcFrom", first_expense.get('vendor', 'N/A'))
    
    # Calculate total tax amount
    total_tax = expenses_data[['gst_amount', 'pst_amount', 'hst_amount']].sum().sum()
    create_sub_element(row_header, "TaxAmnt", f"{total_tax:.2f}")
    
    create_sub_element(row_header, "TotAmnt", f"{report_data.get('total_amount', 0):.2f}")
    create_sub_element(row_header, "ExCurrencyId", first_expense.get('currency', 'CAD')).set("MemberName", "CurrencyCode")

    # Create Details (Line Items)
    details = ET.SubElement(record, "Details")
    for _, expense_row in expenses_data.iterrows():
        detail = ET.SubElement(details, "Detail", {"Table": "PurcDet", "TableType": "2"})
        rows_detail = ET.SubElement(detail, "Rows")
        
        line_items = json.loads(expense_row.get('line_items', '[]')) if expense_row.get('line_items') else []
        if not line_items: # If no line items, use the main expense as one line
            line_items = [{"description": expense_row.get('description'), "price": expense_row.get('amount')}]

        for item in line_items:
            row_detail = ET.SubElement(rows_detail, "Row")
            # Per your request, Qty is hard-coded to 1
            create_sub_element(row_detail, "Qty", "1")
            create_sub_element(row_detail, "UnitPrice", f"{item.get('price', 0):.2f}")
            # The XML has a 'description' field under Item, but the sample doesn't show it.
            # We can add it if needed: create_sub_element(row_detail, "Description", item.get('description'))

    # Pretty print the XML
    rough_string = ET.tostring(record, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")


# --- FUNCTION MODIFIED ---
def add_expense_item(report_id, expense_date, vendor, description, amount, currency='CAD', category_id=None, receipt_path=None, ocr_text=None, gst_amount=None, pst_amount=None, hst_amount=None, line_items=None):
    """Adds a new expense item, now including the currency."""
    supabase = init_connection()
    try:
        supabase.table('expenses').insert({
            "report_id": report_id, "expense_date": str(expense_date), "vendor": vendor,
            "description": description, "amount": amount, "category_id": category_id,
            "receipt_path": receipt_path, "ocr_text": ocr_text, "gst_amount": gst_amount,
            "pst_amount": pst_amount, "hst_amount": hst_amount,
            "line_items": json.dumps(line_items) if line_items else None,
            "currency": currency # Add currency to the insert
        }).execute()
        return True
    except Exception as e:
        st.error(f"Error saving an expense item: {e}")
        return False

# --- All other functions remain the same as the last working version ---
# (fetch_all_users_for_auth, register_user, get_user_role, etc.)
# ... The full code for all other utility functions goes here ...
