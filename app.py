"""Streamlit application for the SIH26034 MVP."""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

from components.dashboard import render_dashboard
from components.results import render_results
from components.styles import inject_css
from components.upload import inspection_form
from src.compliance import overall_status, review_score
from src.extractor import extract_fields
from src.normalizer import normalize_field
from src.ocr import run_ocr
from src.preprocessing import preprocess_image
from src.report import write_csv, write_pdf
from src.repository import Repository
from src.rule_engine import load_rules, validate_fields

ROOT = Path(__file__).parent
RULES_PATH = ROOT / "data" / "rules" / "legal_rules.json"
repo = Repository(ROOT / "data" / "app.db")

st.set_page_config(page_title="SIH26034 Compliance Checker", page_icon="⚖️", layout="wide")
inject_css()
st.sidebar.title("SIH26034")
st.sidebar.caption("Packaged Commodity Legal Compliance Checker")
page = st.sidebar.radio("Navigation", ["Dashboard", "New Inspection", "Product Repository", "Inspection History", "Compare Versions", "Rule Library", "Reports", "Review Queue"])
st.markdown('<div class="disclaimer">AI-assisted compliance review only — not legal advice or certification. Verify prototype rules against current official notifications and obtain qualified human review.</div>', unsafe_allow_html=True)

if page == "Dashboard":
    render_dashboard(repo.list_inspections())
elif page == "New Inspection":
    st.title("New package inspection")
    submitted, values = inspection_form()
    if submitted:
        if not values["images"]:
            st.error("Upload at least one package image.")
        else:
            all_text, confidences = [], []
            progress = st.progress(0, "Preprocessing and OCR")
            for index, uploaded in enumerate(values["images"]):
                prepared = preprocess_image(uploaded.getvalue())
                result = run_ocr(prepared.processed)
                all_text.append(result.text)
                if result.confidence is not None:
                    confidences.append(result.confidence)
                progress.progress((index + 1) / len(values["images"]))
            combined = "\n".join(all_text)
            fields = extract_fields(combined, sum(confidences) / len(confidences) if confidences else None, source=f"{len(values['images'])} package image(s)")
            if values["product_name"]:
                fields["commodity_name"] = {"field": "commodity_name", "original_value": values["product_name"], "normalized_value": normalize_field("commodity_name", values["product_name"]), "source_text": "User-provided product information", "ocr_confidence": None, "extraction_confidence": 1.0, "status": "USER PROVIDED"}
            if values["manufacturer"]:
                fields["manufacturer"] = {"field": "manufacturer", "original_value": values["manufacturer"], "normalized_value": normalize_field("manufacturer", values["manufacturer"]), "source_text": "User-provided product information", "ocr_confidence": None, "extraction_confidence": 1.0, "status": "USER PROVIDED"}
            rules_doc = load_rules(RULES_PATH)
            findings = validate_fields(fields, rules_doc["rules"], {"category": values["category"]})
            inspection = {"inspection_id": f"INSP-{uuid.uuid4().hex[:10].upper()}", "product_id": values["product_id"] or f"PRODUCT-{uuid.uuid4().hex[:6].upper()}", "product_name": values["product_name"] or fields.get("commodity_name", {}).get("normalized_value", "Unknown"), "manufacturer": values["manufacturer"] or fields.get("manufacturer", {}).get("normalized_value", "Unknown"), "category": values["category"], "inspection_date": datetime.now(timezone.utc).isoformat(), "ocr_text": combined, "fields": fields, "findings": findings, "overall_status": overall_status(findings), "review_score": review_score(findings), "rule_version": rules_doc["metadata"]["version"]}
            repo.save_inspection(inspection)
            st.session_state["last_inspection"] = inspection
            st.success(f"Inspection saved: {inspection['inspection_id']}")
    if st.session_state.get("last_inspection"):
        render_results(st.session_state["last_inspection"])
elif page in {"Product Repository", "Inspection History"}:
    st.title(page)
    search = st.text_input("Search product, manufacturer, ID, or status")
    records = repo.list_inspections(search)
    st.dataframe([{k: record.get(k) for k in ("inspection_id", "product_id", "product_name", "manufacturer", "inspection_date", "overall_status")} for record in records], use_container_width=True, hide_index=True)
elif page == "Rule Library":
    st.title("Prototype rule library")
    document = load_rules(RULES_PATH)
    st.warning(document["metadata"]["disclaimer"])
    st.dataframe(document["rules"], use_container_width=True, hide_index=True)
elif page == "Review Queue":
    st.title("Human review queue")
    records = [r for r in repo.list_inspections() if any(f.get("status") == "NEEDS REVIEW" or f.get("severity") == "HIGH" for f in r.get("findings", []))]
    st.dataframe([{k: r.get(k) for k in ("inspection_id", "product_name", "inspection_date", "overall_status")} for r in records], use_container_width=True, hide_index=True)
elif page == "Reports":
    st.title("Reports")
    records = repo.list_inspections()
    if records:
        selected = st.selectbox("Inspection", records, format_func=lambda r: r["inspection_id"])
        col1, col2 = st.columns(2)
        csv_path = write_csv(selected, ROOT / "reports" / f"{selected['inspection_id']}.csv")
        pdf_path = write_pdf(selected, ROOT / "reports" / f"{selected['inspection_id']}.pdf")
        col1.download_button("Download CSV", csv_path.read_bytes(), csv_path.name, "text/csv")
        col2.download_button("Download PDF", pdf_path.read_bytes(), pdf_path.name, "application/pdf")
    else:
        st.info("No saved inspections yet.")
elif page == "Compare Versions":
    st.title("Compare inspection versions")
    records = repo.list_inspections()
    if len(records) < 2:
        st.info("Save at least two inspections to compare versions.")
    else:
        left, right = st.columns(2)
        old = left.selectbox("Previous scan", records, 0, format_func=lambda r: r["inspection_id"])
        new = right.selectbox("New scan", records, 1, format_func=lambda r: r["inspection_id"])
        old_map = {f["field"]: f for f in old.get("findings", [])}
        new_map = {f["field"]: f for f in new.get("findings", [])}
        changed = [{"field": field, "previous": old_map.get(field, {}).get("status"), "new": new_map.get(field, {}).get("status")} for field in sorted(set(old_map) | set(new_map)) if old_map.get(field, {}).get("status") != new_map.get(field, {}).get("status")]
        st.dataframe(changed, use_container_width=True, hide_index=True)
