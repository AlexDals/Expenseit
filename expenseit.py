import streamlit as st
import pandas as pd
import pytesseract
from PIL import Image
import re
from datetime import datetime, date
import io
import base64
from typing import Dict, List, Optional, Tuple
import json
import fitz  # PyMuPDF for PDF processing
import pdf2image
from pdf2image import convert_from_bytes

# Configure page
st.set_page_config(
    page_title="Expense Report OCR",
    page_icon="💳",
    layout="wide"
)

# Initialize session state
if 'expenses' not in st.session_state:
    st.session_state.expenses = []

class ExpenseExtractor:
    """Extract expense information from OCR text"""
    
    @staticmethod
    def extract_amount(text: str) -> Optional[float]:
        """Extract monetary amount from text"""
        # Look for patterns like $12.34, 12.34, $12, etc.
        patterns = [
            r'\$\s*(\d+(?:,\d{3})*(?:\.\d{2})?)',  # $123.45
            r'(\d+(?:,\d{3})*\.\d{2})',            # 123.45
            r'TOTAL[:\s]*\$?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)',  # TOTAL: $123.45
            r'AMOUNT[:\s]*\$?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)', # AMOUNT: $123.45
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                # Get the largest amount (likely the total)
                amounts = [float(match.replace(',', '')) for match in matches]
                return max(amounts)
        return None
    
    @staticmethod
    def extract_tax_details(text: str) -> Dict[str, float]:
        """Extract detailed tax information from text"""
        taxes = {}
        text_lines = text.split('\n')
        
        # Common tax patterns
        tax_patterns = {
            'sales_tax': [
                r'sales?\s*tax[:\s]*\$?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)',
                r'tax[:\s]*\$?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)',
                r'st[:\s]*\$?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)'
            ],
            'gst': [
                r'gst[:\s]*\$?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)',
                r'goods?\s*(?:and\s*)?services?\s*tax[:\s]*\$?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)'
            ],
            'hst': [
                r'hst[:\s]*\$?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)',
                r'harmonized?\s*(?:sales?\s*)?tax[:\s]*\$?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)'
            ],
            'pst': [
                r'pst[:\s]*\$?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)',
                r'provincial?\s*(?:sales?\s*)?tax[:\s]*\$?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)'
            ],
            'qst': [
                r'qst[:\s]*\$?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)',
                r'quebec?\s*(?:sales?\s*)?tax[:\s]*\$?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)'
            ],
            'vat': [
                r'vat[:\s]*\$?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)',
                r'value\s*added\s*tax[:\s]*\$?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)'
            ],
            'service_charge': [
                r'service\s*(?:charge|fee)[:\s]*\$?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)',
                r'gratuity[:\s]*\$?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)'
            ],
            'tip': [
                r'tip[:\s]*\$?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)',
                r'gratuity[:\s]*\$?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)'
            ]
        }
        
        # Extract each type of tax
        for tax_type, patterns in tax_patterns.items():
            for pattern in patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                if matches:
                    try:
                        amount = float(matches[0].replace(',', ''))
                        if amount > 0:
                            taxes[tax_type] = amount
                            break
                    except (ValueError, IndexError):
                        continue
        
        return taxes
    
    @staticmethod
    def extract_subtotal(text: str) -> Optional[float]:
        """Extract subtotal (pre-tax amount) from text"""
        patterns = [
            r'subtotal[:\s]*\$?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)',
            r'sub[:\s]*\$?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)',
            r'before\s*tax[:\s]*\$?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                try:
                    return float(matches[0].replace(',', ''))
                except (ValueError, IndexError):
                    continue
        return None
    
    @staticmethod
    def extract_date(text: str) -> Optional[str]:
        """Extract date from text"""
        patterns = [
            r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',    # MM/DD/YYYY or MM-DD-YYYY
            r'(\d{4}[/-]\d{1,2}[/-]\d{1,2})',      # YYYY-MM-DD
            r'(\w+ \d{1,2}, \d{4})',               # January 1, 2024
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text)
            if matches:
                return matches[0]
        return None
    
    @staticmethod
    def extract_merchant(text: str) -> Optional[str]:
        """Extract merchant name from text"""
        lines = text.split('\n')
        # Usually the merchant name is in the first few lines
        for line in lines[:5]:
            line = line.strip()
            if len(line) > 2 and not re.match(r'^\d+[/-]\d+', line):
                # Skip lines that look like dates, phone numbers, or addresses
                if not re.search(r'\d{3}[-.]?\d{3}[-.]?\d{4}', line):
                    return line
        return None
    
    @staticmethod
    def categorize_expense(text: str, merchant: str = None) -> str:
        """Categorize expense based on text content"""
        text_lower = text.lower()
        merchant_lower = merchant.lower() if merchant else ""
        
        categories = {
            'Food & Dining': ['restaurant', 'cafe', 'coffee', 'pizza', 'burger', 'food', 'dining', 'lunch', 'dinner', 'breakfast'],
            'Transportation': ['uber', 'lyft', 'taxi', 'gas', 'fuel', 'parking', 'metro', 'train', 'bus'],
            'Office Supplies': ['office', 'staples', 'supplies', 'paper', 'pen', 'printer'],
            'Travel': ['hotel', 'flight', 'airline', 'accommodation', 'booking'],
            'Entertainment': ['movie', 'theater', 'entertainment', 'netflix', 'spotify'],
            'Utilities': ['electric', 'water', 'phone', 'internet', 'utility'],
            'Medical': ['pharmacy', 'doctor', 'medical', 'hospital', 'clinic'],
            'Shopping': ['amazon', 'store', 'shop', 'retail', 'walmart', 'target']
        }
        
        for category, keywords in categories.items():
            if any(keyword in text_lower or keyword in merchant_lower for keyword in keywords):
                return category
        
        return 'Other'

def extract_text_from_pdf(pdf_file) -> str:
    """Extract text from PDF file using multiple methods"""
    try:
        # Method 1: Direct text extraction using PyMuPDF
        pdf_bytes = pdf_file.read()
        pdf_file.seek(0)  # Reset file pointer
        
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        text = ""
        
        for page in doc:
            text += page.get_text()
        
        doc.close()
        
        # If direct extraction yields good results, return it
        if len(text.strip()) > 50:
            return text
        
        # Method 2: Convert PDF to images and use OCR
        st.info("PDF contains mostly images. Converting to images for OCR...")
        images = convert_from_bytes(pdf_bytes, dpi=300, first_page=1, last_page=3)  # Limit to first 3 pages
        
        ocr_text = ""
        for i, image in enumerate(images):
            st.info(f"Processing page {i+1}...")
            page_text = perform_ocr(image)
            ocr_text += f"\n--- Page {i+1} ---\n{page_text}\n"
        
        return ocr_text if ocr_text.strip() else text
        
    except Exception as e:
        st.error(f"Error processing PDF: {str(e)}")
        return ""

def perform_ocr(image: Image.Image) -> str:
    """Perform OCR on uploaded image"""
    try:
        # Convert image to RGB if necessary
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Perform OCR with better config for receipts
        custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.,/$%:()-+= '
        text = pytesseract.image_to_string(image, config=custom_config)
        return text
    except Exception as e:
        st.error(f"OCR Error: {str(e)}")
        return ""

def create_download_link(df: pd.DataFrame, filename: str, file_format: str) -> str:
    """Create download link for dataframe"""
    if file_format == 'CSV':
        csv = df.to_csv(index=False)
        b64 = base64.b64encode(csv.encode()).decode()
        href = f'<a href="data:file/csv;base64,{b64}" download="{filename}.csv">Download {file_format}</a>'
    else:  # Excel
        output = io.BytesIO()
        df.to_excel(output, index=False, engine='openpyxl')
        xlsx_data = output.getvalue()
        b64 = base64.b64encode(xlsx_data).decode()
        href = f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="{filename}.xlsx">Download {file_format}</a>'
    
    return href

# Main App Layout
st.title("💳 Expense Report OCR App")
st.markdown("Upload receipts and automatically extract expense information using OCR")

# Sidebar for navigation
with st.sidebar:
    st.header("Navigation")
    tab_choice = st.radio("Choose Section:", ["Add Expenses", "View & Edit", "Export Data", "Analytics"])

# Add Expenses Tab
if tab_choice == "Add Expenses":
    st.header("📷 Add New Expense")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("Upload Receipt Image or PDF")
        uploaded_file = st.file_uploader(
            "Choose an image or PDF file", 
            type=['png', 'jpg', 'jpeg', 'pdf'],
            help="Upload a clear image of your receipt or a PDF document"
        )
        
        if uploaded_file is not None:
            file_type = uploaded_file.type
            
            if file_type == "application/pdf":
                st.info("PDF file uploaded. Processing...")
                
                if st.button("Extract Information from PDF", type="primary"):
                    with st.spinner("Processing PDF document..."):
                        # Extract text from PDF
                        pdf_text = extract_text_from_pdf(uploaded_file)
                        
                        if pdf_text.strip():
                            st.success("PDF processing completed successfully!")
                            
                            # Extract information
                            extractor = ExpenseExtractor()
                            amount = extractor.extract_amount(pdf_text)
                            subtotal = extractor.extract_subtotal(pdf_text)
                            tax_details = extractor.extract_tax_details(pdf_text)
                            expense_date = extractor.extract_date(pdf_text)
                            merchant = extractor.extract_merchant(pdf_text)
                            category = extractor.categorize_expense(pdf_text, merchant)
                            
                            # Store extracted data in session state for editing
                            st.session_state.temp_expense = {
                                'amount': amount or 0.0,
                                'subtotal': subtotal or 0.0,
                                'tax_details': tax_details,
                                'date': expense_date or str(date.today()),
                                'merchant': merchant or "",
                                'category': category,
                                'ocr_text': pdf_text,
                                'file_type': 'pdf'
                            }
                            
                            st.experimental_rerun()
                        else:
                            st.error("Could not extract text from PDF. Please try with a different file.")
            
            else:  # Image file
                image = Image.open(uploaded_file)
                st.image(image, caption="Uploaded Receipt", use_column_width=True)
                
                if st.button("Extract Information from Image", type="primary"):
                    with st.spinner("Processing image with OCR..."):
                        # Perform OCR
                        ocr_text = perform_ocr(image)
                        
                        if ocr_text.strip():
                            st.success("OCR completed successfully!")
                            
                            # Extract information
                            extractor = ExpenseExtractor()
                            amount = extractor.extract_amount(ocr_text)
                            subtotal = extractor.extract_subtotal(ocr_text)
                            tax_details = extractor.extract_tax_details(ocr_text)
                            expense_date = extractor.extract_date(ocr_text)
                            merchant = extractor.extract_merchant(ocr_text)
                            category = extractor.categorize_expense(ocr_text, merchant)
                            
                            # Store extracted data in session state for editing
                            st.session_state.temp_expense = {
                                'amount': amount or 0.0,
                                'subtotal': subtotal or 0.0,
                                'tax_details': tax_details,
                                'date': expense_date or str(date.today()),
                                'merchant': merchant or "",
                                'category': category,
                                'ocr_text': ocr_text,
                                'file_type': 'image'
                            }
                            
                            st.experimental_rerun()
                        else:
                            st.error("Could not extract text from image. Please try with a clearer image.")
    
    with col2:
        st.subheader("Expense Details")
        
        # Check if we have extracted data
        if hasattr(st.session_state, 'temp_expense'):
            temp_expense = st.session_state.temp_expense
            
            # Editable form with extracted data
            with st.form("expense_form"):
                st.write("**Main Expense Information**")
                
                # Basic expense info
                col_form1, col_form2 = st.columns(2)
                with col_form1:
                    total_amount = st.number_input("Total Amount ($)", value=temp_expense['amount'], min_value=0.0, step=0.01)
                    subtotal = st.number_input("Subtotal ($)", value=temp_expense.get('subtotal', 0.0), min_value=0.0, step=0.01, help="Amount before taxes")
                
                with col_form2:
                    expense_date = st.date_input("Date", value=pd.to_datetime(temp_expense['date']).date() if temp_expense['date'] else date.today())
                    merchant = st.text_input("Merchant/Vendor", value=temp_expense['merchant'])
                
                categories = ['Food & Dining', 'Transportation', 'Office Supplies', 'Travel', 'Entertainment', 'Utilities', 'Medical', 'Shopping', 'Other']
                category = st.selectbox("Category", categories, index=categories.index(temp_expense['category']))
                
                description = st.text_area("Description (Optional)")
                
                # Tax Details Section
                st.write("**Tax Breakdown**")
                tax_details = temp_expense.get('tax_details', {})
                
                # Create input fields for each detected tax type
                updated_taxes = {}
                tax_types = ['sales_tax', 'gst', 'hst', 'pst', 'qst', 'vat', 'service_charge', 'tip']
                tax_labels = {
                    'sales_tax': 'Sales Tax',
                    'gst': 'GST',
                    'hst': 'HST', 
                    'pst': 'PST',
                    'qst': 'QST',
                    'vat': 'VAT',
                    'service_charge': 'Service Charge',
                    'tip': 'Tip/Gratuity'
                }
                
                # Display tax inputs in columns
                tax_col1, tax_col2 = st.columns(2)
                
                for i, tax_type in enumerate(tax_types):
                    with tax_col1 if i % 2 == 0 else tax_col2:
                        tax_value = st.number_input(
                            tax_labels[tax_type] + " ($)",
                            value=tax_details.get(tax_type, 0.0),
                            min_value=0.0,
                            step=0.01,
                            key=f"tax_{tax_type}"
                        )
                        if tax_value > 0:
                            updated_taxes[tax_type] = tax_value
                
                # Additional custom tax
                st.write("**Additional Tax (Optional)**")
                custom_tax_name = st.text_input("Custom Tax Name", placeholder="e.g., City Tax, Environmental Fee")
                custom_tax_amount = st.number_input("Custom Tax Amount ($)", min_value=0.0, step=0.01)
                
                if custom_tax_name and custom_tax_amount > 0:
                    updated_taxes[custom_tax_name.lower().replace(' ', '_')] = custom_tax_amount
                
                # Calculate totals
                total_tax = sum(updated_taxes.values())
                calculated_total = subtotal + total_tax
                
                # Display calculation summary
                st.write("**Calculation Summary**")
                st.write(f"Subtotal: ${subtotal:.2f}")
                st.write(f"Total Tax: ${total_tax:.2f}")
                st.write(f"Calculated Total: ${calculated_total:.2f}")
                if abs(calculated_total - total_amount) > 0.01:
                    st.warning(f"⚠️ Difference between entered total (${total_amount:.2f}) and calculated total (${calculated_total:.2f}): ${abs(calculated_total - total_amount):.2f}")
                
                col_a, col_b = st.columns(2)
                with col_a:
                    submit = st.form_submit_button("Add Expense", type="primary")
                with col_b:
                    clear = st.form_submit_button("Clear Form")
                
                if submit and total_amount > 0:
                    new_expense = {
                        'Date': expense_date.strftime('%Y-%m-%d'),
                        'Merchant': merchant,
                        'Total_Amount': total_amount,
                        'Subtotal': subtotal,
                        'Total_Tax': total_tax,
                        'Category': category,
                        'Description': description,
                        'Added': datetime.now().strftime('%Y-%m-%d %H:%M')
                    }
                    
                    # Add individual tax fields
                    for tax_type, amount in updated_taxes.items():
                        new_expense[tax_labels.get(tax_type, tax_type.replace('_', ' ').title())] = amount
                    
                    st.session_state.expenses.append(new_expense)
                    st.success("Expense added successfully!")
                    
                    # Clear temp data
                    if hasattr(st.session_state, 'temp_expense'):
                        del st.session_state.temp_expense
                    st.experimental_rerun()
                
                if clear:
                    if hasattr(st.session_state, 'temp_expense'):
                        del st.session_state.temp_expense
                    st.experimental_rerun()
            
            # Show extracted text
            with st.expander("View Extracted Text"):
                file_type = temp_expense.get('file_type', 'unknown')
                st.write(f"**Source:** {file_type.upper()}")
                st.text_area("Extracted Results", temp_expense['ocr_text'], height=200, disabled=True)
                
                # Show detected tax details
                if temp_expense.get('tax_details'):
                    st.write("**Auto-detected Taxes:**")
                    for tax_type, amount in temp_expense['tax_details'].items():
                        st.write(f"- {tax_labels.get(tax_type, tax_type.replace('_', ' ').title())}: ${amount:.2f}")
        
        else:
            st.info("Upload and process a receipt image or PDF to see extracted information here.")

# View & Edit Tab
elif tab_choice == "View & Edit":
    st.header("📋 View & Edit Expenses")
    
    if st.session_state.expenses:
        df = pd.DataFrame(st.session_state.expenses)
        
        # Display summary
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Expenses", f"${df['Total_Amount'].sum():.2f}")
        with col2:
            st.metric("Number of Expenses", len(df))
        with col3:
            st.metric("Total Tax Paid", f"${df['Total_Tax'].sum():.2f}")
        with col4:
            st.metric("Average Amount", f"${df['Total_Amount'].mean():.2f}")
        
        # Filters
        st.subheader("Filters")
        col1, col2 = st.columns(2)
        
        with col1:
            selected_categories = st.multiselect("Filter by Category", df['Category'].unique(), default=df['Category'].unique())
        
        with col2:
            date_range = st.date_input("Date Range", value=[pd.to_datetime(df['Date']).min().date(), pd.to_datetime(df['Date']).max().date()], key="date_filter")
        
        # Filter dataframe
        filtered_df = df[df['Category'].isin(selected_categories)]
        if len(date_range) == 2:
            filtered_df = filtered_df[
                (pd.to_datetime(filtered_df['Date']).dt.date >= date_range[0]) &
                (pd.to_datetime(filtered_df['Date']).dt.date <= date_range[1])
            ]
        
        # Display filtered data
        st.subheader("Expense Data")
        
        # Configure column display
        column_config = {
            "Total_Amount": st.column_config.NumberColumn("Total Amount", format="$%.2f"),
            "Subtotal": st.column_config.NumberColumn("Subtotal", format="$%.2f"),
            "Total_Tax": st.column_config.NumberColumn("Total Tax", format="$%.2f"),
            "Date": st.column_config.DateColumn("Date"),
        }
        
        # Add tax column configs dynamically
        tax_columns = [col for col in filtered_df.columns if col not in ['Date', 'Merchant', 'Total_Amount', 'Subtotal', 'Total_Tax', 'Category', 'Description', 'Added']]
        for tax_col in tax_columns:
            if filtered_df[tax_col].dtype in ['float64', 'int64']:
                column_config[tax_col] = st.column_config.NumberColumn(tax_col, format="$%.2f")
        
        edited_df = st.data_editor(
            filtered_df,
            use_container_width=True,
            num_rows="dynamic",
            column_config=column_config
        )
        
        # Update session state if data was edited
        if not edited_df.equals(filtered_df):
            # Update the original expenses list
            st.session_state.expenses = edited_df.to_dict('records')
            st.success("Changes saved!")
    
    else:
        st.info("No expenses added yet. Go to 'Add Expenses' to start adding expenses.")

# Export Data Tab
elif tab_choice == "Export Data":
    st.header("📤 Export Data")
    
    if st.session_state.expenses:
        df = pd.DataFrame(st.session_state.expenses)
        
        st.subheader("Export Options")
        
        col1, col2 = st.columns(2)
        
        with col1:
            export_format = st.selectbox("Export Format", ["CSV", "Excel"])
            filename = st.text_input("Filename", value=f"expenses_{datetime.now().strftime('%Y%m%d')}")
        
        with col2:
            st.subheader("Preview")
            st.dataframe(df.head(), use_container_width=True)
        
        # Generate download link
        if st.button("Generate Download Link", type="primary"):
            download_link = create_download_link(df, filename, export_format)
            st.markdown(download_link, unsafe_allow_html=True)
            st.success(f"Download link generated for {export_format} file!")
        
        # Display summary before export
        st.subheader("Export Summary")
        st.write(f"**Total Records:** {len(df)}")
        st.write(f"**Total Amount:** ${df['Total_Amount'].sum():.2f}")
        st.write(f"**Total Tax Paid:** ${df['Total_Tax'].sum() if 'Total_Tax' in df.columns else 0:.2f}")
        st.write(f"**Date Range:** {df['Date'].min()} to {df['Date'].max()}")
        
        # Tax breakdown summary
        tax_columns = [col for col in df.columns if col not in ['Date', 'Merchant', 'Total_Amount', 'Subtotal', 'Total_Tax', 'Category', 'Description', 'Added']]
        if tax_columns:
            st.write("**Tax Breakdown:**")
            for tax_col in tax_columns:
                if df[tax_col].sum() > 0:
                    st.write(f"- {tax_col}: ${df[tax_col].sum():.2f}")
    
    else:
        st.info("No expenses to export. Add some expenses first.")

# Analytics Tab
elif tab_choice == "Analytics":
    st.header("📊 Expense Analytics")
    
    if st.session_state.expenses:
        df = pd.DataFrame(st.session_state.expenses)
        df['Date'] = pd.to_datetime(df['Date'])
        df['Month'] = df['Date'].dt.to_period('M')
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Expenses by Category
            st.subheader("Expenses by Category")
            category_summary = df.groupby('Category')['Total_Amount'].sum().sort_values(ascending=False)
            st.bar_chart(category_summary)
            
            # Top expenses
            st.subheader("Top 5 Expenses")
            top_expenses = df.nlargest(5, 'Total_Amount')[['Date', 'Merchant', 'Total_Amount', 'Category']]
            st.dataframe(top_expenses, use_container_width=True)
            
            # Tax Analysis
            st.subheader("Tax Analysis")
            if 'Total_Tax' in df.columns:
                total_tax_paid = df['Total_Tax'].sum()
                avg_tax_rate = (total_tax_paid / df['Subtotal'].sum() * 100) if df['Subtotal'].sum() > 0 else 0
                st.write(f"**Total Tax Paid:** ${total_tax_paid:.2f}")
                st.write(f"**Average Tax Rate:** {avg_tax_rate:.1f}%")
                
                # Individual tax breakdown
                tax_columns = [col for col in df.columns if col not in ['Date', 'Merchant', 'Total_Amount', 'Subtotal', 'Total_Tax', 'Category', 'Description', 'Added']]
                if tax_columns:
                    st.write("**Tax Type Breakdown:**")
                    for tax_col in tax_columns:
                        if df[tax_col].sum() > 0:
                            tax_total = df[tax_col].sum()
                            tax_pct = (tax_total / total_tax_paid * 100) if total_tax_paid > 0 else 0
                            st.write(f"- {tax_col}: ${tax_total:.2f} ({tax_pct:.1f}%)")
        
        with col2:
            # Monthly spending
            st.subheader("Monthly Spending Trend")
            monthly_spending = df.groupby('Month')['Total_Amount'].sum()
            st.line_chart(monthly_spending)
            
            # Monthly tax trend
            st.subheader("Monthly Tax Trend")
            if 'Total_Tax' in df.columns:
                monthly_tax = df.groupby('Month')['Total_Tax'].sum()
                st.line_chart(monthly_tax)
            
            # Category breakdown
            st.subheader("Category Breakdown")
            for category in df['Category'].unique():
                category_total = df[df['Category'] == category]['Total_Amount'].sum()
                category_pct = (category_total / df['Total_Amount'].sum()) * 100
                category_tax = df[df['Category'] == category]['Total_Tax'].sum() if 'Total_Tax' in df.columns else 0
                st.write(f"**{category}:** ${category_total:.2f} ({category_pct:.1f}%) | Tax: ${category_tax:.2f}")
    
    else:
        st.info("No expenses to analyze. Add some expenses first.")

# Footer
st.markdown("---")
st.markdown("Built with Streamlit • OCR powered by Tesseract")
