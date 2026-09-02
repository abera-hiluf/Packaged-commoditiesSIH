"""Streamlit presentation layer for the SIH26034 prototype."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from components.results import render_results
from components.styles import inject_css
from src.repository import Repository
from src.rule_engine import load_rules

ROOT = Path(__file__).parent
RULES_PATH = ROOT / "data" / "rules" / "legal_rules.json"
repo = Repository(ROOT / "data" / "compliance.db")


def _status_icon(status: str) -> str:
    return {"COMPLIANT": "✓", "NON_COMPLIANT": "✕", "REVIEW_REQUIRED": "⚠"}.get(status, "•")


def render_header() -> None:
    st.title("Package Compliance Intelligence")
    st.caption("AI-assisted packaged commodity declaration inspection")
    st.info("Prototype for decision support. Results require human verification.")


def render_about() -> None:
    st.title("About this prototype")
    st.write("This system helps reviewers inspect package declarations through OCR, structured extraction, normalization, configurable prototype rules, and evidence provenance.")
    st.code("Image → OCR → Extraction → Normalization → Applicability → Rule Engine → Evidence → Review", language="text")
    st.write("Technology: Python, Streamlit, OpenCV, Tesseract OCR, and SQLite.")
    st.warning("Prototype rules are configurable demonstration rules, not a substitute for verified current legal requirements or qualified legal review.")


def render_new_inspection() -> None:
    st.header("New Inspection")
    st.write("Upload clear images of the front, back, and side panels of the package.")
    uploads = st.file_uploader("Package images", type=["png", "jpg", "jpeg", "webp"], accept_multiple_files=True)
    if uploads:
        preview_columns = st.columns(min(4, len(uploads)))
        for index, upload in enumerate(uploads):
            with preview_columns[index % len(preview_columns)]:
                st.image(upload, caption=upload.name, use_container_width=True)
    st.subheader("Optional product information")
    product_name = st.text_input("Product name")
    category = st.text_input("Category", value="General")
    manufacturer = st.text_input("Manufacturer")
    package_type = st.text_input("Package type", value="Retail package")
    origin = st.text_input("Origin")
    if st.button("Analyze Package", type="primary", disabled=not uploads):
        if not uploads:
            st.warning("Please upload at least one package image.")
            return
        product = {"product_id": f"PRODUCT-{id(uploads)}", "product_name": product_name, "category": category, "manufacturer": manufacturer, "package_type": package_type, "origin": origin}
        # Keep OpenCV, NumPy, and pytesseract out of the initial page import.
        from src.service import image_id_for_name, process_inspection

        rules = load_rules(RULES_PATH)["rules"]
        image_inputs = []
        upload_images = {}
        for index, upload in enumerate(uploads):
            image_id = image_id_for_name(upload.name, index)
            image_bytes = upload.getvalue()
            image_inputs.append({"image_id": image_id, "name": upload.name, "bytes": image_bytes})
            upload_images[image_id] = image_bytes
        with st.spinner("Preparing images, reading package text, evaluating findings, and preparing evidence…"):
            result = process_inspection(product, image_inputs, rules, repository=repo)
        st.session_state["current_result"] = result
        st.session_state["current_uploads"] = upload_images
    if st.session_state.get("current_result"):
        render_results(st.session_state["current_result"], st.session_state.get("current_uploads", {}), repo)


def render_history() -> None:
    st.header("Inspection History")
    search = st.text_input("Search inspection, product, manufacturer, or status")
    records = repo.list_inspections(search)
    if not records:
        st.info("No inspections found. Run the explicit demo seed command or create a new inspection.")
        return
    selected_id = st.selectbox("Select inspection", [record["inspection_id"] for record in records])
    selected = next(record for record in records if record["inspection_id"] == selected_id)
    st.dataframe([{key: selected.get(key) for key in ("inspection_id", "product_id", "product_name", "inspection_date", "overall_status")}], use_container_width=True, hide_index=True)
    findings = repo.get_findings_for_inspection(selected_id)
    st.subheader("Findings")
    for finding in findings:
        with st.expander(f"{finding.get('declaration', 'Finding').replace('_', ' ').title()} — {finding.get('status')}"):
            st.write(finding.get("message"))
            st.write(finding.get("reason"))
            evidence = repo.get_evidence_for_finding(finding["finding_id"])
            for item in evidence:
                st.write(item.get("source_text"), item.get("image_path"))


def render_review_action(finding: dict) -> None:
    st.write("Human review")
    review_status = st.selectbox("Review status", ["VERIFIED", "REJECTED", "CORRECTED"], key=f"review_status_{finding['finding_id']}")
    reviewer = st.text_input("Reviewer name", key=f"reviewer_{finding['finding_id']}")
    correction = st.text_input("Corrected value (optional)", key=f"correction_{finding['finding_id']}")
    comment = st.text_area("Review comment", key=f"comment_{finding['finding_id']}")
    if st.button("Save review", key=f"save_review_{finding['finding_id']}"):
        repo.update_review_status(finding["finding_id"], review_status, reviewer or "Reviewer", correction or None, comment or None)
        st.success("Review action saved without overwriting original evidence.")


def main() -> None:
    st.set_page_config(page_title="Package Compliance Intelligence", page_icon="⚖", layout="wide")
    inject_css()
    render_header()
    st.sidebar.title("SIH26034")
    page = st.sidebar.radio("Workspace", ["New Inspection", "Dashboard", "Inspection History", "About"])
    st.sidebar.caption("Prototype • Human verification required")
    if page == "New Inspection":
        render_new_inspection()
    elif page == "Dashboard":
        # Plotly/pandas are only needed on the dashboard, not on first load.
        from components.dashboard import render_dashboard

        render_dashboard(repo.list_inspections())
    elif page == "Inspection History":
        render_history()
    else:
        render_about()
    st.markdown("---")
    st.caption("SIH26034 Prototype | AI-assisted compliance decision support | Human verification required.")


if __name__ == "__main__":
    main()
