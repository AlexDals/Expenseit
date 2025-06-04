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

def perform_ocr(image: Image.Image) -> str:
    """Perform OCR on uploaded image"""
    try:
        # Convert image to RGB if necessary
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Perform OCR
        text = pytesseract.image_to_string(image)
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
        st.subheader("Upload Receipt Image")
        uploaded_file = st.file_uploader(
            "Choose an image file", 
            type=['png', 'jpg', 'jpeg'],
            help="Upload a clear image of your receipt"
        )
        
        if uploaded_file is not None:
            image = Image.open(uploaded_file)
            st.image(image, caption="Uploaded Receipt", use_column_width=True)
            
            if st.button("Extract Information", type="primary"):
                with st.spinner("Processing image with OCR..."):
                    # Perform OCR
                    ocr_text = perform_ocr(image)
                    
                    if ocr_text.strip():
                        st.success("OCR completed successfully!")
                        
                        # Extract information
                        extractor = ExpenseExtractor()
                        amount = extractor.extract_amount(ocr_text)
                        expense_date = extractor.extract_date(ocr_text)
                        merchant = extractor.extract_merchant(ocr_text)
                        category = extractor.categorize_expense(ocr_text, merchant)
                        
                        # Store extracted data in session state for editing
                        st.session_state.temp_expense = {
                            'amount': amount or 0.0,
                            'date': expense_date or str(date.today()),
                            'merchant': merchant or "",
                            'category': category,
                            'ocr_text': ocr_text
                        }
                        
                        st.experimental_rerun()
    
    with col2:
        st.subheader("Expense Details")
        
        # Check if we have extracted data
        if hasattr(st.session_state, 'temp_expense'):
            temp_expense = st.session_state.temp_expense
            
            # Editable form with extracted data
            with st.form("expense_form"):
                amount = st.number_input("Amount ($)", value=temp_expense['amount'], min_value=0.0, step=0.01)
                
                expense_date = st.date_input("Date", value=pd.to_datetime(temp_expense['date']).date() if temp_expense['date'] else date.today())
                
                merchant = st.text_input("Merchant/Vendor", value=temp_expense['merchant'])
                
                categories = ['Food & Dining', 'Transportation', 'Office Supplies', 'Travel', 'Entertainment', 'Utilities', 'Medical', 'Shopping', 'Other']
                category = st.selectbox("Category", categories, index=categories.index(temp_expense['category']))
                
                description = st.text_area("Description (Optional)")
                
                col_a, col_b = st.columns(2)
                with col_a:
                    submit = st.form_submit_button("Add Expense", type="primary")
                with col_b:
                    clear = st.form_submit_button("Clear Form")
                
                if submit and amount > 0:
                    new_expense = {
                        'Date': expense_date.strftime('%Y-%m-%d'),
                        'Merchant': merchant,
                        'Amount': amount,
                        'Category': category,
                        'Description': description,
                        'Added': datetime.now().strftime('%Y-%m-%d %H:%M')
                    }
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
            
            # Show extracted OCR text
            with st.expander("View Extracted Text"):
                st.text_area("OCR Results", temp_expense['ocr_text'], height=150, disabled=True)
        
        else:
            st.info("Upload and process a receipt image to see extracted information here.")

# View & Edit Tab
elif tab_choice == "View & Edit":
    st.header("📋 View & Edit Expenses")
    
    if st.session_state.expenses:
        df = pd.DataFrame(st.session_state.expenses)
        
        # Display summary
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Expenses", f"${df['Amount'].sum():.2f}")
        with col2:
            st.metric("Number of Expenses", len(df))
        with col3:
            st.metric("Average Amount", f"${df['Amount'].mean():.2f}")
        
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
        edited_df = st.data_editor(
            filtered_df,
            use_container_width=True,
            num_rows="dynamic",
            column_config={
                "Amount": st.column_config.NumberColumn("Amount", format="$%.2f"),
                "Date": st.column_config.DateColumn("Date"),
            }
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
        st.write(f"**Total Amount:** ${df['Amount'].sum():.2f}")
        st.write(f"**Date Range:** {df['Date'].min()} to {df['Date'].max()}")
    
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
            category_summary = df.groupby('Category')['Amount'].sum().sort_values(ascending=False)
            st.bar_chart(category_summary)
            
            # Top expenses
            st.subheader("Top 5 Expenses")
            top_expenses = df.nlargest(5, 'Amount')[['Date', 'Merchant', 'Amount', 'Category']]
            st.dataframe(top_expenses, use_container_width=True)
        
        with col2:
            # Monthly spending
            st.subheader("Monthly Spending Trend")
            monthly_spending = df.groupby('Month')['Amount'].sum()
            st.line_chart(monthly_spending)
            
            # Category breakdown
            st.subheader("Category Breakdown")
            for category in df['Category'].unique():
                category_total = df[df['Category'] == category]['Amount'].sum()
                category_pct = (category_total / df['Amount'].sum()) * 100
                st.write(f"**{category}:** ${category_total:.2f} ({category_pct:.1f}%)")
    
    else:
        st.info("No expenses to analyze. Add some expenses first.")

# Footer
st.markdown("---")
st.markdown("Built with Streamlit • OCR powered by Tesseract")
