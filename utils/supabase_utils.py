import streamlit as st
from supabase import create_client, Client
import pandas as pd
from datetime import datetime
import os
import json

# ... (init_connection and all user-related functions remain the same) ...
# ... (add_report, add_expense_item, etc. remain the same) ...

# --- NEW CATEGORY MANAGEMENT FUNCTIONS ---

def get_all_categories():
    """Fetches all expense categories from the database."""
    supabase = init_connection()
    try:
        response = supabase.table('categories').select("id, name, gl_account").order('name', desc=False).execute()
        return response.data
    except Exception as e:
        st.error(f"Error fetching categories: {e}")
        return []

def add_category(name, gl_account):
    """Adds a new category to the database."""
    supabase = init_connection()
    try:
        # Check if category name already exists
        if supabase.table('categories').select('id').eq('name', name).execute().data:
            st.warning(f"Category '{name}' already exists.")
            return False
        
        supabase.table('categories').insert({
            "name": name,
            "gl_account": gl_account
        }).execute()
        return True
    except Exception as e:
        st.error(f"Error adding category: {e}")
        return False

def update_category(category_id, name, gl_account):
    """Updates an existing category's details."""
    supabase = init_connection()
    try:
        supabase.table('categories').update({
            "name": name,
            "gl_account": gl_account
        }).eq('id', category_id).execute()
        return True
    except Exception as e:
        st.error(f"Error updating category: {e}")
        return False

def delete_category(category_id):
    """Deletes a category from the database."""
    supabase = init_connection()
    try:
        supabase.table('categories').delete().eq('id', category_id).execute()
        return True
    except Exception as e:
        st.error(f"Error deleting category: {e}")
        return False


# --- FUNCTION MODIFIED ---
def add_expense_item(report_id, expense_date, vendor, description, amount, category_id=None, receipt_path=None, ocr_text=None, gst_amount=None, pst_amount=None, hst_amount=None, line_items=None):
    """Adds a new expense item, now including the overall category_id."""
    supabase = init_connection()
    try:
        supabase.table('expenses').insert({
            "report_id": report_id,
            "expense_date": str(expense_date),
            "vendor": vendor,
            "description": description,
            "amount": amount,
            "category_id": category_id, # Add category_id to the insert
            "receipt_path": receipt_path,
            "ocr_text": ocr_text,
            "gst_amount": gst_amount,
            "pst_amount": pst_amount,
            "hst_amount": hst_amount,
            "line_items": json.dumps(line_items) if line_items else None
        }).execute()
        return True
    except Exception as e:
        st.error(f"Error saving an expense item: {e}")
        return False

# --- FUNCTION MODIFIED ---
def get_expenses_for_report(report_id):
    """Fetches all expense items for a report, including the category name."""
    supabase = init_connection()
    try:
        # Join with categories table to get the category name for display
        response = supabase.table('expenses').select("*, category_name:categories(name)").eq('report_id', report_id).execute()
        
        # The result from Supabase nests the category name, so we need to flatten it
        expenses = response.data
        for expense in expenses:
            if expense.get('categories'):
                expense['category_name'] = expense['categories']['name']
                del expense['categories']
            else:
                expense['category_name'] = "N/A"

        return pd.DataFrame(expenses)
    except Exception as e:
        st.error(f"Error fetching expense items: {e}")
        return pd.DataFrame()
