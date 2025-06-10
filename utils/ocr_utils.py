import pytesseract
from PIL import Image
import io
import re
import fitz  # PyMuPDF
import cv2  # OpenCV
import numpy as np
from google.cloud import vision
import streamlit as st
from itertools import combinations

# --- GOOGLE VISION API AND IMAGE PREPROCESSING (No Changes) ---
@st.cache_resource
def get_vision_client():
    try:
        credentials_dict = dict(st.secrets.google_credentials)
        client = vision.ImageAnnotatorClient.from_service_account_info(credentials_dict)
        return client
    except Exception as e:
        st.error(f"Could not initialize Google Vision API client: {e}. Please check your Streamlit secrets.")
        st.stop()

def preprocess_image_for_ocr(image_bytes):
    try:
        img_array = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        scale_percent = 200
        width = int(img.shape[1] * scale_percent / 100)
        height = int(img.shape[0] * scale_percent / 100)
        dim = (width, height)
        resized = cv2.resize(gray, dim, interpolation = cv2.INTER_CUBIC)
        _, final_img = cv2.threshold(resized, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        _, processed_img_bytes = cv2.imencode('.png', final_img)
        return processed_img_bytes.tobytes()
    except Exception:
        img_array = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
        _, processed_img_bytes = cv2.imencode('.png', thresh)
        return processed_img_bytes.tobytes()

def extract_text_from_file(uploaded_file):
    client = get_vision_client()
    file_bytes = uploaded_file.getvalue()
    try:
        if uploaded_file.type == "application/pdf":
            full_text = ""
            with fitz.open(stream=file_bytes, filetype="pdf") as doc:
                for page in doc:
                    pix = page.get_pixmap(dpi=300)
                    processed_bytes = preprocess_image_for_ocr(pix.tobytes("png"))
                    image = vision.Image(content=processed_bytes)
                    response = client.document_text_detection(image=image)
                    if response.error.message: raise Exception(response.error.message)
                    full_text += response.full_text_annotation.text + "\n"
            return full_text
        elif uploaded_file.type in ["image/png", "image/jpeg", "image/jpg"]:
            processed_bytes = preprocess_image_for_ocr(file_bytes)
            image = vision
