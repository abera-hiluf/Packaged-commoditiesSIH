"""Small visual system for the Streamlit prototype."""

import streamlit as st


def inject_css() -> None:
    st.markdown("""<style>
    .block-container {max-width: 1400px; padding-top: 2rem;}
    .metric-card {background:#f4f7fb;border:1px solid #dbe4ee;border-radius:12px;padding:16px;}
    .disclaimer {background:#fff8e6;border-left:4px solid #e0a100;padding:12px;border-radius:4px;}
    </style>""", unsafe_allow_html=True)


def status_badge(status: str) -> str:
    colors = {"COMPLIANT": "#16803c", "WARNING": "#a36400", "NON-COMPLIANT": "#b42318", "NEEDS REVIEW": "#6b46c1"}
    return f'<span style="background:{colors.get(status, "#64748b")};color:white;padding:4px 9px;border-radius:12px;font-size:.8rem">{status}</span>'

