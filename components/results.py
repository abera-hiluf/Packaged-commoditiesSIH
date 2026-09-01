"""Inspection result rendering."""

import streamlit as st

from .styles import status_badge


def render_results(inspection: dict) -> dict:
    st.subheader("Overall review status")
    st.markdown(status_badge(inspection.get("overall_status", "NEEDS REVIEW")), unsafe_allow_html=True)
    st.caption("Review score is an application prioritization indicator, not a legal percentage.")
    st.metric("Compliance Review Score", f"{inspection.get('review_score', 0)}/100")
    for finding in inspection.get("findings", []):
        with st.expander(f"{finding.get('field', '').replace('_', ' ').title()} — {finding.get('status')}"):
            st.markdown(status_badge(finding.get("status", "NEEDS REVIEW")), unsafe_allow_html=True)
            st.write("Value:", finding.get("value") or "Not detected")
            st.write("Evidence:", finding.get("evidence") or "No matching OCR evidence")
            st.write("Reason:", finding.get("reason"))
            st.write("Rule:", f"{finding.get('rule_id')} — {finding.get('rule_description')}")
            st.write("OCR confidence:", finding.get("ocr_confidence") if finding.get("ocr_confidence") is not None else "Unavailable")
    return inspection

