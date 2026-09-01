"""Application service that orchestrates the complete inspection pipeline."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any, Iterable

from .applicability import evaluate_rules_applicability
from .evidence import attach_evidence_to_finding, create_field_evidence
from .extractor import extract_fields_from_images
from .normalizer import normalize_extracted_fields
from .ocr import run_ocr
from .preprocessing import preprocess_image
from .repository import Repository
from .rule_engine import evaluate_all_rules, overall_product_status, summarize_findings

logger = logging.getLogger(__name__)


def _image_id(path: str | Path, index: int) -> str:
    stem = Path(path).stem.strip().lower().replace(" ", "_") or f"image_{index + 1}"
    return stem


def _unique_image_ids(image_paths: Iterable[str | Path]) -> list[str]:
    used: set[str] = set()
    result = []
    for index, path in enumerate(image_paths):
        candidate = _image_id(path, index)
        if candidate in used:
            candidate = f"{candidate}_{index + 1}"
        used.add(candidate)
        result.append(candidate)
    return result


def _image_evidence(extracted: dict[str, Any], normalized: dict[str, Any], image_paths: dict[str, str]) -> list[dict[str, Any]]:
    if extracted.get("status") == "CONFLICT":
        candidates = extracted.get("candidates", [])
    else:
        candidates = [extracted]
    records = []
    for candidate in candidates:
        candidate_normalized = normalized
        if normalized.get("normalization_status") == "CONFLICT":
            for normalized_candidate in normalized.get("candidates", []):
                if normalized_candidate.get("original_value") == candidate.get("value", candidate.get("original_value")):
                    candidate_normalized = normalized_candidate
                    break
        records.append(create_field_evidence(candidate, candidate_normalized, image_paths.get(candidate.get("image_id"))))
    return records


def process_inspection(product: dict[str, Any], image_paths: Iterable[str | Path], rules: list[dict[str, Any]], inspection_metadata: dict[str, Any] | None = None, repository: Repository | None = None) -> dict[str, Any]:
    """Run all pipeline stages and return a complete, persistence-backed result."""
    metadata = inspection_metadata or {}
    paths = [str(path) for path in image_paths]
    inspection_id = metadata.get("inspection_id") or f"INSP-{uuid.uuid4().hex[:10].upper()}"
    logger.info("PROCESSING_STARTED inspection_id=%s image_count=%s", inspection_id, len(paths))
    result: dict[str, Any] = {"inspection_id": inspection_id, "status": "PROCESSING", "overall_status": "REVIEW_REQUIRED", "product": product, "images": [], "ocr": [], "extracted_fields": {}, "normalized_fields": {}, "applicability": [], "findings": [], "evidence": [], "summary": {}, "errors": []}
    image_ids = _unique_image_ids(paths)
    image_paths_by_id = dict(zip(image_ids, paths))
    ocr_inputs = []
    successful_images = 0

    for image_id, path in zip(image_ids, paths):
        image_record = {"image_id": image_id, "image_path": path, "status": "PROCESSING"}
        try:
            prepared = preprocess_image(path)
            ocr_result = run_ocr(prepared["processed"])
            ocr_payload = ocr_result.as_dict() if hasattr(ocr_result, "as_dict") else dict(ocr_result)
            ocr_payload["image_id"] = image_id
            image_record.update({"status": "COMPLETED", "metadata": prepared["metadata"]})
            result["ocr"].append(ocr_payload)
            ocr_inputs.append(ocr_payload)
            successful_images += 1
            if ocr_payload.get("error"):
                image_record["status"] = "COMPLETED_WITH_WARNING"
                result["errors"].append({"stage": "ocr", "image_id": image_id, "error": ocr_payload["error"]})
            logger.info("OCR_COMPLETED inspection_id=%s image_id=%s", inspection_id, image_id)
        except Exception as exc:
            message = str(exc) or "Image processing failed."
            image_record.update({"status": "FAILED", "error": message})
            result["errors"].append({"stage": "image_processing", "image_id": image_id, "error": message})
            logger.warning("IMAGE_PROCESSING_FAILED inspection_id=%s image_id=%s", inspection_id, image_id)
        result["images"].append(image_record)

    if not ocr_inputs:
        result["status"] = "FAILED"
        result["errors"].append({"stage": "pipeline", "error": "No image could be processed."})
        return _persist_result(result, product, paths, repository)

    extracted = extract_fields_from_images(ocr_inputs)
    normalized = normalize_extracted_fields(extracted)
    result["extracted_fields"] = extracted.fields
    result["normalized_fields"] = normalized
    result["applicability"] = evaluate_rules_applicability(product, rules)
    result["findings"] = evaluate_all_rules(rules, normalized, result["applicability"])
    result["summary"] = summarize_findings(result["findings"])
    result["overall_status"] = overall_product_status(result["findings"])
    logger.info("RULE_VALIDATION_COMPLETED inspection_id=%s", inspection_id)

    evidence_by_field: dict[str, list[dict[str, Any]]] = {}
    for field_name, extracted_field in extracted.fields.items():
        normalized_field = normalized.get(field_name, {})
        evidence_by_field[field_name] = _image_evidence(extracted_field, normalized_field, image_paths_by_id)
        result["evidence"].extend(evidence_by_field[field_name])
    for finding in result["findings"]:
        linked = attach_evidence_to_finding(finding, evidence_by_field.get(finding.get("declaration"), []))
        finding.clear()
        finding.update(linked)
    result["status"] = "COMPLETED" if successful_images else "FAILED"
    if result["overall_status"] == "REVIEW_REQUIRED" and result["status"] == "COMPLETED":
        result["status"] = "COMPLETED"
    return _persist_result(result, product, paths, repository)


def _persist_result(result: dict[str, Any], product: dict[str, Any], paths: list[str], repository: Repository | None) -> dict[str, Any]:
    if repository is None:
        return result
    try:
        repository.create_product({"product_id": product.get("product_id") or f"PRODUCT-{result['inspection_id']}", "product_name": product.get("product_name"), "category": product.get("category"), "manufacturer": product.get("manufacturer")})
    except Exception:
        if not repository.get_product(product.get("product_id") or f"PRODUCT-{result['inspection_id']}"):
            raise
    product_id = product.get("product_id") or f"PRODUCT-{result['inspection_id']}"
    if not repository.get_inspection(result["inspection_id"]):
        repository.create_inspection({"inspection_id": result["inspection_id"], "product_id": product_id, "inspection_date": result.get("inspection_date"), "overall_status": result.get("overall_status")})
    for image in result.get("images", []):
        try:
            repository.save_image({"image_id": image["image_id"], "inspection_id": result["inspection_id"], "image_path": image.get("image_path"), "image_type": image["image_id"]})
        except Exception:
            pass
    for ocr in result.get("ocr", []):
        repository.save_ocr_result(ocr)
    for field in result.get("extracted_fields", {}).values():
        repository.save_extracted_field(result["inspection_id"], field)
    for field in result.get("normalized_fields", {}).values():
        repository.save_normalized_field(result["inspection_id"], field)
    for applicability in result.get("applicability", []):
        repository.save_applicability_result(result["inspection_id"], applicability)
    for finding in result.get("findings", []):
        repository.save_compliance_finding(result["inspection_id"], finding)
        for evidence in result.get("evidence", []):
            if evidence.get("evidence_id") in finding.get("evidence_ids", []):
                repository.save_evidence(evidence, finding["finding_id"])
    result["persistence_status"] = "SAVED"
    logger.info("PERSISTENCE_COMPLETED inspection_id=%s", result["inspection_id"])
    return result
