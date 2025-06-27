# File: utils/ui_utils.py
import streamlit as st

def hide_streamlit_pages_nav():
    st.markdown(
        """
        <style>
          /* Hide built-in multi-page nav */
          nav[aria-label="App pages"],
          div[data-testid="stSidebarNav"] {
            display: none !important;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )
