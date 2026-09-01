"""Dashboard metrics and lightweight charts."""

import pandas as pd
import plotly.express as px
import streamlit as st


def render_dashboard(inspections: list[dict]) -> None:
    st.title("Compliance review dashboard")
    statuses = [i.get("overall_status", "NEEDS REVIEW") for i in inspections]
    cols = st.columns(5)
    for col, label in zip(cols, ["Products", "Inspections", "Compliant", "Non-compliant", "Needs review"]):
        value = len({i.get("product_id") for i in inspections}) if label == "Products" else len(inspections) if label == "Inspections" else statuses.count(label.upper().replace(" ", "-"))
        col.metric(label, value)
    if statuses:
        frame = pd.DataFrame({"Status": statuses})
        st.plotly_chart(px.histogram(frame, x="Status", color="Status", title="Review status distribution"), use_container_width=True)
    st.subheader("Recent inspections")
    st.dataframe(pd.DataFrame([{k: i.get(k) for k in ("inspection_id", "product_name", "inspection_date", "overall_status")} for i in inspections]), use_container_width=True, hide_index=True)

