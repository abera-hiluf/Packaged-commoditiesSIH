"""Upload and analysis controls."""

import streamlit as st


def inspection_form():
    with st.form("inspection_form"):
        st.subheader("Product information")
        product_name = st.text_input("Product name")
        manufacturer = st.text_input("Manufacturer")
        category = st.text_input("Category", value="General")
        product_id = st.text_input("Product ID")
        images = st.file_uploader("Package images (front/back/side/top)", type=["png", "jpg", "jpeg"], accept_multiple_files=True)
        submitted = st.form_submit_button("Analyze package", type="primary")
    return submitted, {"product_name": product_name, "manufacturer": manufacturer, "category": category, "product_id": product_id, "images": images}

