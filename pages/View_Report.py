import streamlit as st
from utils import supabase_utils as su
import pandas as pd
import io # Required for in-memory Excel file
import re # --- FIX: Import the 're' module for regular expressions ---

# --- CORRECTED AUTHENTICATION GUARD ---
if not st.session_state.get("authentication_status"):
    st.warning("Please log in to access this page.")
    st.stop() # Stop execution if not authenticated
# --- END OF CORRECTION ---

st.title("🗂️ View Submitted Expense Reports")
username = st.session_state.get("username")
user_id = su.get_user_id_by_username(username)

if not user_id:
    st.error("Could not identify user. Please log in again.")
    st.stop()

reports_df = su.get_reports_for_user(user_id)

if reports_df.empty:
    st.info("You have not submitted any expense reports yet.")
else:
    st.subheader("Your Reports Summary")
    # Format the options for the selectbox
    report_options = {f"{row['report_name']} (Submitted: {pd.to_datetime(row['submission_date']).strftime('%Y-%m-%d')})": row['id'] for index, row in reports_df.iterrows()}
    
    # Add a placeholder for the user to not have a report pre-selected
    report_options_list = ["-- Select a report --"] + list(report_options.keys())
    selected_report_display_name = st.selectbox("Select a report to view details:", options=report_options_list)

   # ... (code at the top remains the same) ...

    if selected_report_display_name != "-- Select a report --":
        # ... (code to get expenses_df remains the same) ...
        
        if not expenses_df.empty:
            # --- LOOP THROUGH EACH EXPENSE TO DISPLAY DETAILS ---
            for index, row in expenses_df.iterrows():
                st.markdown(f"#### Expense: {row['vendor']} - ${row['amount']:.2f}")
                
                exp_col1, exp_col2 = st.columns(2)
                with exp_col1:
                    st.write(f"**Date:** {row['expense_date']}")
                    st.write(f"**Description:** {row['description']}")
                with exp_col2:
                    st.write(f"**GST/TPS:** ${row['gst_amount'] or 0:.2f}")
                    st.write(f"**PST/QST:** ${row['pst_amount'] or 0:.2f}")
                    st.write(f"**HST/TVH:** ${row['hst_amount'] or 0:.2f}")

                # --- NEW: Display Line Items and Receipt Image ---
                with st.expander("View Details (Line Items & Receipt)"):
                    if row['line_items'] and isinstance(row['line_items'], list) and len(row['line_items']) > 0:
                        st.write("**Line Items**")
                        line_items_df = pd.DataFrame(row['line_items'])
                        st.dataframe(line_items_df)
                    else:
                        st.write("No line items were extracted for this expense.")

                    if row['receipt_path']:
                        st.write("**Receipt Image**")
                        receipt_url = su.get_receipt_public_url(row['receipt_path'])
                        st.image(receipt_url)
                
                st.markdown("---")

            # ... (Export buttons logic remains the same) ...
