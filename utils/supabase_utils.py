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
    """Initializes and returns a Supabase client."""
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key)
    except KeyError:
        st.error("Supabase credentials not found.")
        st.stop()

# --- DEFINITIVE XML EXPORTER ---
def generate_report_xml(report_data: pd.Series, expenses_data: pd.DataFrame, submitter_name: str) -> str:
    """
    Generates an XML string for a given report, exactly matching the required format
    by including all placeholder and default fields.
    """
    def create_sub_element(parent, tag, text, attributes=None):
        # This helper ensures that even if text is None, an empty tag is created.
        element = ET.SubElement(parent, tag, attrib=attributes or {})
        element.text = str(text) if text is not None and pd.notna(text) else ""
        return element

    all_categories = get_all_categories()
    category_id_to_gl_map = {cat['id']: cat['gl_account'] for cat in all_categories}

    # --- Root Element ---
    record = ET.Element("Record", {
        "SystemDBVersion": "3676", "ExportFileFormatVersion": "1.002",
        "ExportDate": datetime.now().strftime("%Y-%m-%d"),
        "DataObjectID": "{02E10F25-EDA3-4A1C-AF1C-741067C309B1}", "AllowDataSetEvents": "0"
    })
    
    # --- Header Section ---
    header = ET.SubElement(record, "Header", {"Table": "PurcHdr", "TableType": "1"})
    
    # --- Header -> DefaultValues ---
    default_values_hdr = ET.SubElement(header, "DefaultValues")
    create_sub_element(default_values_hdr, "Member", datetime.now().strftime("%-m/%-d/%Y")).set("Name", "PurcDate")
    create_sub_element(default_values_hdr, "Member", "1").set("Name", "ExchangeRate")
    create_sub_element(default_values_hdr, "Member", "0").set("Name", "ShipAmnt")
    create_sub_element(default_values_hdr, "Member", "50").set("Name", "PurcType")
    create_sub_element(default_values_hdr, "Member", "0").set("Name", "SurchargeAmnt")
    create_sub_element(default_values_hdr, "Member", "0").set("Name", "ShipTax")
    create_sub_element(default_values_hdr, "Member", "DALS Lighting, Inc.\n80 Boul. de la Seigneurie E.\nBlainville Quebec J7C 4N1\nCanada\nTel.: 450 430-1818\nFax: 450-430-1850").set("Name", "ShipTo")
    create_sub_element(default_values_hdr, "Member", "1").set("Name", "x00198411_TransportsExchangeRate")
    create_sub_element(default_values_hdr, "Member", "1").set("Name", "x00198411_BrokeragesExchangerate")
    create_sub_element(default_values_hdr, "Member", "0").set("Name", "VirtualPaidAmnt")
    create_sub_element(default_values_hdr, "Member", "0").set("Name", "VirtualShipAmnt")
    create_sub_element(default_values_hdr, "Member", "1").set("Name", "x00198411_CustomsExchangeRate")
    create_sub_element(default_values_hdr, "Member", "0").set("Name", "PaidAmnt")
    create_sub_element(default_values_hdr, "Member", "1").set("Name", "ExCurrencyId")
    create_sub_element(default_values_hdr, "Member", "1").set("Name", "ExTemplId")

    # --- Header -> Rows -> Row (Main Report Data) ---
    rows_header = ET.SubElement(header, "Rows")
    row_header = ET.SubElement(rows_header, "Row")
    
    first_expense = expenses_data.iloc[0] if not expenses_data.empty else {}
    currency = first_expense.get('currency', 'CAD') if pd.notna(first_expense.get('currency')) else 'CAD'
    total_amount_str = f"{report_data.get('total_amount', 0):.4f}"
    
    create_sub_element(row_header, "ExSuppId", first_expense.get('vendor', ''), {"MemberName": "SuppId", "SourceField": "SuppId", "DataType": "2"})
    create_sub_element(row_header, "PurcDate", str(report_data.get('submission_date', ''))[:10], {"xmlns:dt": "urn:schemas-microsoft-com:datatypes", "dt:dt": "date"})
    create_sub_element(row_header, "DocNo", report_data.get('report_name', ''))
    create_sub_element(row_header, "ExTermId", "N/A", {"MemberName": "Descr", "SourceField": "Descr", "DataType": "2"})
    create_sub_element(row_header, "Remarks", report_data.get('report_name', ''))
    create_sub_element(row_header, "ExchangeRate", "1.00000", {"xmlns:dt": "urn:schemas-microsoft-com:datatypes", "dt:dt": "r8"})
    create_sub_element(row_header, "PurcFrom", first_expense.get('vendor', ''))
    total_tax = (expenses_data['gst_amount'].sum() or 0) + (expenses_data['pst_amount'].sum() or 0) + (expenses_data['hst_amount'].sum() or 0)
    create_sub_element(row_header, "TaxAmnt", f"{total_tax:.4f}", {"xmlns:dt": "urn:schemas-microsoft-com:datatypes", "dt:dt": "fixed.14.4"})
    create_sub_element(row_header, "TaxHoldbackAmnt", "0.0000", {"xmlns:dt": "urn:schemas-microsoft-com:datatypes", "dt:dt": "fixed.14.4"})
    create_sub_element(row_header, "TotAmnt", total_amount_str, {"xmlns:dt": "urn:schemas-microsoft-com:datatypes", "dt:dt": "fixed.14.4"})
    create_sub_element(row_header, "ShipAmnt", "0.0000", {"xmlns:dt": "urn:schemas-microsoft-com:datatypes", "dt:dt": "fixed.14.4"})
    create_sub_element(row_header, "PurcType", "50", {"IsRawPrimaryKey": "-1"})
    create_sub_element(row_header, "SurchargeAmnt", "0.0000", {"xmlns:dt": "urn:schemas-microsoft-com:datatypes", "dt:dt": "fixed.14.4"})
    create_sub_element(row_header, "ShipVia", "")
    create_sub_element(row_header, "ShipTax", "0", {"xmlns:dt": "urn:schemas-microsoft-com:datatypes", "dt:dt": "int"})
    create_sub_element(row_header, "ShipTo", "DALS Lighting, Inc.\n80 Boul. de la Seigneurie E.\nBlainville Quebec J7C 4N1\nCanada\nTel.: 450 430-1818\nFax: 450-430-1850")
    create_sub_element(row_header, "UpdatedBy", submitter_name)
    create_sub_element(row_header, "CreatedBy", submitter_name)
    create_sub_element(row_header, "PaidAmnt", "0.0000")
    create_sub_element(row_header, "PurchAmnt", total_amount_str)
    create_sub_element(row_header, "PaidExGLAcctId", "1001", {"MemberName": "GLAcctId", "SourceField": "GLAcctId", "DataType": "2"})
    create_sub_element(row_header, "ExPmtMethId", "Check", {"MemberName": "PmtMeth", "SourceField": "PmtMeth", "DataType": "2"})
    create_sub_element(row_header, "ExCurrencyId", currency, {"MemberName": "CurrencyCode", "SourceField": "CurrencyCode", "DataType": "2"})
    create_sub_element(row_header, "ExTemplId", "Purchase Order", {"MemberName": "TmplName", "SourceField": "TmplName", "DataType": "2"})
    create_sub_element(row_header, "Balance", total_amount_str)

    # --- Details Section (for Line Items) ---
    details = ET.SubElement(record, "Details")
    for _, expense_row in expenses_data.iterrows():
        detail = ET.SubElement(details, "Detail", {"Table": "PurcDet", "TableType": "2", "Rows": "1"})
        default_values_det = ET.SubElement(detail, "DefaultValues")
        create_sub_element(default_values_det, "Member", "0").set("Name", "TaxIncluded")
        
        rows_detail = ET.SubElement(detail, "Rows")
        
        line_items_str = expense_row.get('line_items')
        line_items = json.loads(line_items_str) if line_items_str and isinstance(line_items_str, str) else []
        if not line_items:
            # If no line items, create one from the main expense itself
            line_items = [{"description": expense_row.get('description'), "price": expense_row.get('amount'), "category_id": expense_row.get('category_id')}]

        for item in line_items:
            if item and item.get('price') is not None:
                row_detail = ET.SubElement(rows_detail, "Row")
                
                # Correctly look up the GL account for the item's assigned category
                item_category_id = item.get('category_id')
                gl_account = category_id_to_gl_map.get(item_category_id, "")
                price_str = f"{item.get('price', 0):.4f}"
                
                create_sub_element(row_detail, "BaseRowTotal", price_str, {"xmlns:dt": "urn:schemas-microsoft-com:datatypes", "dt:dt": "fixed.14.4"})
                create_sub_element(row_detail, "ExPurcAcctId", gl_account, {"MemberName": "GLAcctId", "SourceField": "GLAcctId", "DataType": "2"})
                create_sub_element(row_detail, "Qty", "1", {"xmlns:dt": "urn:schemas-microsoft-com:datatypes", "dt:dt": "fixed.14.4"})
                create_sub_element(row_detail, "TaxIncluded", "0", {"xmlns:dt": "urn:schemas-microsoft-com:datatypes", "dt:dt": "boolean"})
                create_sub_element(row_detail, "UnitPrice", price_str, {"xmlns:dt": "urn:schemas-microsoft-com:datatypes", "dt:dt": "fixed.14.4"})
    
    # Convert the ElementTree object to a nicely formatted string
    rough_string = ET.tostring(record, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    # Return the pretty string, ensuring the XML declaration is included
    return reparsed.toxml()


# --- ALL OTHER FUNCTIONS ---
# (The full code for all other utility functions is included below for completeness)
def fetch_all_users_for_auth():
    # ...
# ... etc
