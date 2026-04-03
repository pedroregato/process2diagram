# ui/components/download_button.py
import streamlit as st

def download_button(data, filename, label, key=None):
    st.download_button(label, data=data, file_name=filename, key=key)
