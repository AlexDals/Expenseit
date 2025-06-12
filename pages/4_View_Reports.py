import streamlit as st
from utils import supabase_utils as su
import pandas as pd
import io
import re
import json

# ... (Authentication guard and initial setup at the top remain the same) ...

    if selected_report_display_name != "-- Select a report --":
        # ... (code to select a report and display details remains the same) ...

        # --- Export Buttons Section ---
        if not original_expenses_df.empty:
            st.subheader("Export This Full Report")
            
            clean_report_name = re.sub(r'[^a-zA-Z0-9\s]', '', selected_report_display_name.split(' (')[0]).replace(' ', '_')
            
            # --- Prepare data for export ---
            # ... (code to prepare export_df for CSV/Excel remains the same) ...
            
            # --- NEW: Generate XML data ---
            submitter_name = selected_report_details.get('user', {}).get('name', 'N/A')
            xml_data = su.generate_report_xml(
                selected_report_id, 
                selected_report_details, 
                original_expenses_df, 
                submitter_name
            )

            btn_col1, btn_col2, btn_col3 = st.columns(3)
            with btn_col1:
                # ... (CSV Download button remains the same) ...
            with btn_col2:
                # ... (Excel Download button remains the same) ...
            with btn_col3:
                # --- XML Download Button ---
                st.download_button(
                    label="💿 Download as XML",
                    data=xml_data,
                    file_name=f"{clean_report_name}.xml",
                    mime="application/xml",
                    use_container_width=True
                )
