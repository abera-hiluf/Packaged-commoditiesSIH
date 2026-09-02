"""Application service that orchestrates the complete inspection pipeline."""

from __future__ import annotations

import logging
import hashlib
import mimetypes
import uuid
from pathlib import Path
from typing import Any, Iterable

from .applicability import evaluate_rules_applicability
from .evidence import attach_evidence_to_finding, create_field_evidence
from .extractor import extract_fields_from_images
from .normalizer import normalize_extracted_fields
from .ocr import run_ocr, run_ocr_variants
from .preprocessing import preprocess_image
from .repository import Repository
from .rule_engine import evaluate_all_rules, overall_product_status, summarize_findings

logger = logging.getLogger(__name__)


def _image_id(path: str | Path, index: int) -> str:
    stem = Path(path).stem.strip().lower().replace(" ", "_") or f"image_{index + 1}"
    return stem


def image_id_for_name(path: str | Path, index: int = 0) -> str:
    return _image_id(path, index)


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


def _image_input(item: Any, index: int) -> tuple[str, Any, str, dict[str, Any]]:
    """Return stable ID, decodable source, and human-readable name.

    Sources may be paths (CLI/local compatibility), bytes, or dictionaries from
    Streamlit. Bytes are deliberately kept in memory so Cloud does not depend
    on a Windows path or a persistent local filesystem.
    """
    if isinstance(item, dict):
        name = str(item.get("name") or item.get("image_id") or f"image_{index + 1}")
        image_id = str(item.get("image_id") or _image_id(name, index))
        source = item.get("bytes", item.get("data", item.get("path")))
        if source is None:
            raise ValueError(f"Image input '{name}' has no bytes or path.")
        return image_id, source, name, {"mime_type": item.get("mime_type"), "file_size": item.get("file_size")}
    if isinstance(item, (bytes, bytearray, memoryview)):
        name = f"image_{index + 1}"
        return _image_id(name, index), item, name, {}
    name = str(item)
    return _image_id(name, index), item, name, {}


def process_inspection(product: dict[str, Any], image_paths: Iterable[Any], rules: list[dict[str, Any]], inspection_metadata: dict[str, Any] | None = None, repository: Repository | None = None) -> dict[str, Any]:
    """Run all pipeline stages and return a complete, persistence-backed result."""
    metadata = inspection_metadata or {}
    inputs = [_image_input(item, index) for index, item in enumerate(image_paths)]
    paths = [name for _, _, name, _ in inputs]
    inspection_id = metadata.get("inspection_id") or f"INSP-{uuid.uuid4().hex[:10].upper()}"
    logger.info("PROCESSING_STARTED inspection_id=%s image_count=%s", inspection_id, len(paths))
    result: dict[str, Any] = {"inspection_id": inspection_id, "status": "PROCESSING", "overall_status": "REVIEW_REQUIRED", "product": product, "images": [], "ocr": [], "extracted_fields": {}, "normalized_fields": {}, "applicability": [], "findings": [], "evidence": [], "summary": {}, "errors": []}
    # Preserve caller IDs while making duplicate upload names unambiguous.
    used_ids: set[str] = set()
    deduped_inputs = []
    for index, (image_id, source, name, input_metadata) in enumerate(inputs):
        candidate = image_id
        if candidate in used_ids:
            candidate = f"{candidate}_{index + 1}"
        used_ids.add(candidate)
        deduped_inputs.append((candidate, source, name, input_metadata))
    inputs = deduped_inputs
    image_ids = [item[0] for item in inputs]
    image_paths_by_id = {item[0]: item[2] for item in inputs}
    ocr_inputs = []
    successful_images = 0

    for image_id, source, name, input_metadata in inputs:
        source_bytes = bytes(source) if isinstance(source, (bytes, bytearray, memoryview)) else None
        image_record = {"image_id": image_id, "image_name": name, "image_path": name, "status": "PROCESSING", "decoding_status": "PENDING", "preprocessing_status": "PENDING", "file_extension": Path(name).suffix.lower(), "mime_type": input_metadata.get("mime_type") or mimetypes.guess_type(name)[0], "file_size": input_metadata.get("file_size") if input_metadata.get("file_size") is not None else len(source_bytes) if source_bytes is not None else None, "image_sha256": hashlib.sha256(source_bytes).hexdigest() if source_bytes is not None else None}
        try:
            prepared = preprocess_image(source)
            original_image = prepared.get("original")
            dimensions = {"image_width": int(original_image.shape[1]), "image_height": int(original_image.shape[0]), "image_channels": int(1 if original_image.ndim == 2 else original_image.shape[2])} if original_image is not None else {}
            image_record.update({"decoding_status": "SUCCESS", "preprocessing_status": "SUCCESS", **dimensions, "preprocessing_steps": prepared.get("metadata", {}).get("processing_steps", []), "variants_tested": list(prepared.get("variants", {}))})
            ocr_result = run_ocr_variants(prepared["variants"]) if prepared.get("variants") else run_ocr(prepared["processed"])
            ocr_payload = ocr_result.as_dict() if hasattr(ocr_result, "as_dict") else dict(ocr_result)
            ocr_payload["image_id"] = image_id
            ocr_payload["image_name"] = name
            ocr_status = ocr_payload.get("ocr_status")
            if not ocr_status:
                ocr_status = "NO_TEXT" if ocr_payload.get("error") and not ocr_payload.get("text") and "no text" in str(ocr_payload.get("error")).lower() else "FAILED" if ocr_payload.get("error") else "SUCCESS"
            image_record.update({"status": "COMPLETED", "metadata": prepared["metadata"], "ocr_status": ocr_status, "ocr_text_length": len(ocr_payload.get("text", "")), "ocr_confidence": ocr_payload.get("confidence")})
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
            image_record.update({"decoding_status": "FAILED", "preprocessing_status": "FAILED", "ocr_status": "NOT_RUN", "ocr_text_length": 0})
            result["errors"].append({"stage": "image_processing", "image_id": image_id, "error": message})
            logger.warning("IMAGE_PROCESSING_FAILED inspection_id=%s image_id=%s", inspection_id, image_id)
        result["images"].append(image_record)

    if not ocr_inputs:
        result["errors"].append({"stage": "pipeline", "error": "No image could be processed; compliance findings are review-only."})

    extracted = extract_fields_from_images(ocr_inputs)
    normalized = normalize_extracted_fields(extracted)
    readable = [item for item in result["ocr"] if item.get("ocr_status") == "SUCCESS" and item.get("text")]
    if readable:
        confidence_values = [item.get("confidence") for item in readable if item.get("confidence") is not None]
        normalized["label_readability"] = {"field": "label_readability", "original_value": "OCR text detected", "normalized_value": "SUFFICIENT" if not confidence_values or max(confidence_values) >= 60 else "LOW", "normalization_status": "NORMALIZED", "normalization_method": "ocr_diagnostic", "ocr_confidence": max(confidence_values) if confidence_values else None, "source_text": "\n".join(item.get("text", "") for item in readable), "image_id": readable[0].get("image_id")}
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
    for image in result["images"]:
        image["extracted_field_count"] = sum(1 for field in extracted.fields.values() if field.get("image_id") == image["image_id"] or any(candidate.get("image_id") == image["image_id"] for candidate in field.get("candidates", [])))
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
