"""Dashboard metrics and lightweight charts."""

import streamlit as st


def render_dashboard(inspections: list[dict]) -> None:
    st.title("Compliance review dashboard")
    statuses = [i.get("overall_status", "NEEDS REVIEW") for i in inspections]
    cols = st.columns(5)
    for col, label in zip(cols, ["Products", "Inspections", "Compliant", "Non-compliant", "Needs review"]):
        value = len({i.get("product_id") for i in inspections}) if label == "Products" else len(inspections) if label == "Inspections" else statuses.count(label.upper().replace(" ", "-"))
        col.metric(label, value)
    if statuses:
        status_counts = {status: statuses.count(status) for status in sorted(set(statuses))}
        st.subheader("Review status distribution")
        st.bar_chart(status_counts, horizontal=True)
    st.subheader("Recent inspections")
    st.dataframe([{k: i.get(k) for k in ("inspection_id", "product_name", "inspection_date", "overall_status")} for i in inspections], use_container_width=True, hide_index=True)
