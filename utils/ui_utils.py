import streamlit as st

def hide_streamlit_pages_nav():
    """Permanently hide Streamlit's built-in pages sidebar nav."""
    st.markdown(
        """
        <style>
          /* Hide the default multi-page nav and sidebar nav container */
          nav[aria-label="App pages"],
          div[data-testid="stSidebarNav"] {
            display: none !important;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )
