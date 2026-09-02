"""Presentation helpers for inspection results and evidence."""

from __future__ import annotations

from typing import Any

import streamlit as st

from .styles import status_badge


def _evidence_lookup(result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item.get("evidence_id"): item for item in result.get("evidence", [])}


def render_results(result: dict[str, Any], uploaded_images: dict[str, bytes] | None = None, repository: Any = None) -> None:
    """Render backend result; all decisions come from the service result."""
    st.header("Inspection Complete")
    overall = result.get("overall_status", "REVIEW_REQUIRED")
    st.markdown(f"### {_status_label(overall)}")
    if result.get("errors"):
        st.warning("Some processing steps need attention. Review the structured errors below.")
        with st.expander("Processing details"):
            st.json(result["errors"])
    with st.expander("OCR & Processing Details"):
        for image in result.get("images", []):
            image_id = image.get("image_id", "unknown")
            st.markdown(f"**{image.get('image_name', image_id)}** (`{image_id}`)")
            st.write({key: image.get(key) for key in ("decoding_status", "preprocessing_status", "ocr_status", "ocr_text_length", "ocr_confidence", "error") if key in image})
            ocr = next((item for item in result.get("ocr", []) if item.get("image_id") == image_id), None)
            if ocr:
                if ocr.get("ocr_status") == "FAILED":
                    st.error(ocr.get("error") or "OCR engine unavailable/configuration error.")
                elif ocr.get("ocr_status") == "NO_TEXT":
                    st.warning("OCR completed but no usable text was detected.")
                with st.expander(f"Raw OCR text — {image_id}"):
                    st.code(ocr.get("raw_text", ocr.get("text", "")) or "(empty)")
                st.caption(f"Words: {len(ocr.get('words', []))} · Lines: {len(ocr.get('lines', []))}")
    summary = result.get("summary", {})
    cards = st.columns(5)
    for column, label, key in zip(cards, ["Total Rules", "Passed", "Failed", "Warnings", "Needs Review"], ["total_rules", "passed", "failed", "warnings", "needs_review"]):
        column.metric(label, summary.get(key, 0))
    st.subheader("Detected Declarations")
    fields = result.get("normalized_fields", {})
    if fields:
        st.dataframe([{"Field": field.replace("_", " ").title(), "Original value": value.get("original_value"), "Normalized value": value.get("normalized_value"), "Status": value.get("normalization_status"), "Source": value.get("image_id") or "Available evidence"} for field, value in fields.items()], use_container_width=True, hide_index=True)
    else:
        st.info("No declarations were extracted from the available images.")
    evidence = _evidence_lookup(result)
    st.subheader("Compliance Findings")
    for finding in result.get("findings", []):
        title = f"{finding.get('declaration', 'Finding').replace('_', ' ').title()} — {finding.get('status')}"
        with st.expander(title):
            st.markdown(status_badge(finding.get("status", "NEEDS_REVIEW")), unsafe_allow_html=True)
            st.write(finding.get("message", ""))
            st.write("Rule:", finding.get("rule_id"))
            st.write("Severity:", finding.get("severity") or "Configured rule severity")
            st.write("Reason:", finding.get("reason"))
            linked = [evidence[item] for item in finding.get("evidence_ids", []) if item in evidence]
            if linked:
                st.markdown("**Evidence**")
                for item in linked:
                    st.write("Detected text:", item.get("source_text") or "Unavailable")
                    st.write("Image:", item.get("image_id") or "Unavailable")
                    st.write("OCR confidence:", item.get("ocr_confidence") if item.get("ocr_confidence") is not None else "Unavailable")
                    st.write("Extraction confidence:", item.get("extraction_confidence") if item.get("extraction_confidence") is not None else "Unavailable")
                    if item.get("bbox") is not None:
                        st.write("Bounding box:", item["bbox"])
                    if uploaded_images and item.get("image_id") in uploaded_images:
                        st.image(uploaded_images[item["image_id"]], caption=f"Original image: {item['image_id']}", use_container_width=True)
            else:
                st.caption(finding.get("evidence_status", "NO_SUPPORTING_TEXT_DETECTED"))
            if finding.get("status") == "NEEDS_REVIEW" or finding.get("requires_review"):
                st.warning("Human review required. AI assistance does not replace reviewer judgment.")
            if repository is not None and finding.get("finding_id"):
                from app import render_review_action
                render_review_action(finding)


def _status_label(status: str) -> str:
    return {"COMPLIANT": "✓ COMPLIANT", "NON_COMPLIANT": "✕ NON-COMPLIANT", "REVIEW_REQUIRED": "⚠ REVIEW REQUIRED"}.get(status, status)
