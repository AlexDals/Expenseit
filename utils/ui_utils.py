# File: utils/ui_utils.py

import streamlit as st

def apply_global_css():
    """Inject global CSS for a more professional, aligned layout across all pages."""
    st.markdown("""
    <style>
    /* Reduce spacing between elements */
    .block-container .css-12oz5g7.e16nr0p32 {
        padding-top: 0.5rem;
        padding-bottom: 0.5rem;
    }
    /* Style headers */
    h1, h2, h3, .stMarkdown h1, .stMarkdown h2 {
        color: #004b8d;
        font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif;
        margin-bottom: 0.75rem;
    }
    /* Inputs full width */
    .stTextInput>div>div>input,
    .stNumberInput>div>div>input,
    .stSelectbox>div>div>div>select {
        width: 100% !important;
        padding: 0.5rem !important;
        border-radius: 4px !important;
        border: 1px solid #ccc !important;
    }
    /* Button styling */
    .stButton>button {
        background-color: #004b8d !important;
        color: white !important;
        border-radius: 4px !important;
        padding: 0.5rem 1rem !important;
        font-weight: 500 !important;
    }
    .stButton>button:hover {
        background-color: #003366 !important;
    }
    /* Align columns and reduce gutter */
    .css-k1vhr4.egzxvld1 {
        gap: 1rem !important;
    }
    </style>
    """, unsafe_allow_html=True)

def hide_streamlit_pages_nav():
    """Hide Streamlit's built-in pages sidebar nav and apply global CSS."""
    # Hide the default multipage nav and sidebar nav container
    st.markdown(
        """
        <style>
          nav[aria-label="App pages"],
          div[data-testid="stSidebarNav"] {
            display: none !important;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )  # :contentReference[oaicite:2]{index=2}

    # Inject our custom, global styling
    apply_global_css()
