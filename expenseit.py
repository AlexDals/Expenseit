import streamlit as st
import pandas as pd
import pytesseract
from PIL import Image
import fitz  # PyMuPDF

st.title("📄 Expense Report App with OCR")

uploaded_file = st.file_uploader("Upload a receipt (image or PDF)", type=["png", "jpg", "jpeg", "pdf"])

if uploaded_file:
    if uploaded_file.type.startswith("image"):
        image = Image.open(uploaded_file)
        text = pytesseract.image_to_string(image)
    elif uploaded_file.type == "application/pdf":
        doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
        text = " ".join(page.get_text() for page in doc)

    st.subheader("📝 Extracted Text")
    st.text_area("OCR Output", text, height=200)

    # Placeholder for parsing logic
    st.subheader("📊 Expense Summary (Mock Data)")
    data = pd.DataFrame({
        "Category": ["Food", "Travel"],
        "Amount": [120.00, 200.00]
    })
    st.dataframe(data)
    st.metric("Total Expenses", f"${data['Amount'].sum():.2f}")
