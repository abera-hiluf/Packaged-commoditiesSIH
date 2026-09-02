"""Deterministic declaration extraction from OCR text and evidence.

This module identifies what a label appears to declare. It does not normalize
values, determine applicability, or make compliance decisions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable


EXTRACTION_STATUSES = {"EXTRACTED", "NOT_FOUND", "AMBIGUOUS", "CONFLICT"}


@dataclass
class ExtractionResult(dict):
    """Flat field mapping compatible with existing callers plus a structured view."""

    def __init__(self, fields: dict[str, dict[str, Any]], image_results: list[dict[str, Any]] | None = None):
        dict.__init__(self, fields)
        self.image_results = image_results or []

    @property
    def fields(self) -> dict[str, dict[str, Any]]:
        return dict(self)

    def as_dict(self) -> dict[str, Any]:
        return {"fields": self.fields, "images": self.image_results}


def _ocr_payload(ocr_result: Any, image_id: str | None = None) -> dict[str, Any]:
    if hasattr(ocr_result, "as_dict"):
        payload = ocr_result.as_dict()
    elif isinstance(ocr_result, dict):
        payload = dict(ocr_result)
    elif isinstance(ocr_result, str):
        payload = {"text": ocr_result}
    else:
        raise TypeError("ocr_result must be OCRResult, dictionary, or text string")
    payload.setdefault("text", "")
    payload.setdefault("words", [])
    payload.setdefault("lines", [])
    payload["image_id"] = image_id if image_id is not None else payload.get("image_id")
    return payload


def _bbox_for_source(payload: dict[str, Any], source_text: str) -> list[int] | None:
    for line in payload.get("lines", []):
        if line.get("text", "").strip() == source_text.strip():
            return [int(line.get(key, 0)) for key in ("x", "y", "width", "height")]
    return None


def _candidate(field: str, value: str, source_text: str, payload: dict[str, Any], method: str, confidence: float = 0.9, status: str = "EXTRACTED") -> dict[str, Any]:
    return {"field": field, "value": value.strip(), "source_text": source_text.strip(), "ocr_confidence": payload.get("confidence"), "extraction_confidence": confidence, "image_id": payload.get("image_id"), "image_name": payload.get("image_name"), "bbox": _bbox_for_source(payload, source_text), "method": method, "status": status}


def _line_candidates(payload: dict[str, Any]) -> list[tuple[str, str]]:
    lines = [str(line.get("text", "")).strip() for line in payload.get("lines", []) if str(line.get("text", "")).strip()]
    if lines:
        return [(line, line) for line in lines]
    return [(line.strip(), line.strip()) for line in str(payload.get("text", "")).splitlines() if line.strip()]


PATTERNS: dict[str, list[tuple[str, str]]] = {
    "mrp": [(r"(?i)\b(?:m\.?r\.?p\.?|maximum\s+retail\s+price)\s*[:\-]?\s*((?:₹|rs\.?|inr)\s*[0-9][0-9,]*(?:\.[0-9]{1,2})?|[0-9][0-9,]*(?:\.[0-9]{1,2})?)", "regex")],
    "net_quantity": [(r"(?i)\b(?:net\s*(?:quantity|qty|weight|wt)|net\s*(?:qnty|qu?an?t?))\s*[:\-]?\s*([0-9][0-9,.]*\s*(?:kg|kgs?|kilograms?|g|gm|gms?|grams?|ml|millilit(?:re|er)s?|l|lit(?:re|er)s?))\b", "regex")],
    "manufacturer": [(r"(?i)\b(?:manufactured\s*(?:&|and)\s*marketed\s*by|manufactured\s+by|mfd\.?\s+by)\s*[:\-]?\s*(.+)$", "label_context")],
    "packer": [(r"(?i)\b(?:packed\s+by|packer)\s*[:\-]?\s*(.+)$", "label_context")],
    "importer": [(r"(?i)\b(?:imported\s+by|importer)\s*[:\-]?\s*(.+)$", "label_context")],
    "consumer_care": [(r"(?i)\b(?:customer\s+care|consumer\s+care|consumer\s+complaints?|customer\s+service|helpline|toll\s*free)\s*[:\-]?\s*(.*(?:\d{3,}.*|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|https?://\S+).*)$", "label_context")],
    "country_of_origin": [(r"(?i)\b(?:country\s+of\s+origin|made\s+in|product\s+of)\s*[:\-]?\s*([A-Za-z][A-Za-z .'-]{1,})$", "label_context")],
    "manufacture_date": [(r"(?i)\b(?:manufacturing\s+date|date\s+of\s+manufacture|manufactured\s+on|mfd\.?\s*date|mfg\.?\s*date|mfd|mfg)\s*[:\-\.]?\s*([0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{2,4}|[0-9]{1,2}[/-][0-9]{2,4}|[A-Za-z]{3,9}\s+[0-9]{4})\b", "date_context")],
    "packing_date": [(r"(?i)\b(?:packing\s+date|packed\s+on|pkd)\s*[:\-]?\s*([0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{2,4}|[0-9]{1,2}[/-][0-9]{2,4}|[A-Za-z]{3,9}\s+[0-9]{4})\b", "date_context")],
    "import_date": [(r"(?i)\b(?:import\s+date|imported\s+on)\s*[:\-]?\s*([0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{2,4}|[0-9]{1,2}[/-][0-9]{2,4}|[A-Za-z]{3,9}\s+[0-9]{4})\b", "date_context")],
    "best_before": [(r"(?i)\bbest\s+before\s*[:\-]?\s*([^\n]+)$", "label_context")],
    "use_by": [(r"(?i)\b(?:use\s+by|best\s+before\s*/?\s*use\s+by|expiry|expires)\s*[:\-]?\s*([^\n]+)$", "label_context")],
    "unit_sale_price": [(r"(?i)\b(?:unit\s+sale\s+price|price\s+per)\s*[:\-]?\s*([^\n]+)$", "label_context")],
    "commodity_name": [(r"(?i)\b(?:product\s+name|commodity|product)\s*[:\-]\s*(.{2,})$", "label_context")],
}


_PRODUCT_NOISE = re.compile(r"(?i)^(?:ingredients?|nutrition|directions?|barcode|scan|www\.|fssai|batch|lot|mfg|mfd|mrp|net|packed|manufactured|customer|consumer|best|use\s+by|expiry|made\s+in)\b")


def _product_name_candidate(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Use a conservative, label-agnostic heuristic for unlabelled front panels."""
    lines = [line for line, _ in _line_candidates(payload)]
    for index, line in enumerate(lines[:8]):
        cleaned = re.sub(r"[^A-Za-z0-9&' -]", " ", line).strip()
        if _PRODUCT_NOISE.search(cleaned) or len(cleaned) < 3:
            continue
        words = cleaned.split()
        if len(words) == 1 and index + 1 < len(lines):
            next_line = re.sub(r"[^A-Za-z0-9&' -]", " ", lines[index + 1]).strip()
            if len(next_line.split()) >= 2 and not _PRODUCT_NOISE.search(next_line):
                cleaned = f"{cleaned} {next_line}"
                words = cleaned.split()
        if len(words) >= 2 and any(char.isalpha() for char in cleaned):
            return _candidate("commodity_name", cleaned, cleaned, payload, "front_panel_heuristic", 0.65)
    return None


def _extract_from_payload(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    for field, patterns in PATTERNS.items():
        candidates = []
        for source_text, _ in _line_candidates(payload):
            for pattern, method in patterns:
                match = re.search(pattern, source_text)
                if not match:
                    continue
                value = match.group(1).strip()
                if field in {"manufacturer", "packer", "importer"} and "&" in source_text.lower() and field == "manufacturer":
                    candidates.append(_candidate(field, value, source_text, payload, method, 0.55, "AMBIGUOUS"))
                elif field == "mrp" and re.search(r"(?i)subject\s+to\s+change", value):
                    continue
                elif value:
                    candidates.append(_candidate(field, value, source_text, payload, method))
                break
        if candidates:
            found[field] = candidates[0] if len(candidates) == 1 else {"field": field, "status": "CONFLICT", "candidates": candidates, "image_id": payload.get("image_id")}
    if "commodity_name" not in found:
        candidate = _product_name_candidate(payload)
        if candidate:
            found["commodity_name"] = candidate
    return found


def extract_fields(ocr_result: Any, ocr_confidence: float | None = None, source: str | None = None) -> ExtractionResult:
    """Extract declarations from one OCR result without making legal decisions."""
    payload = _ocr_payload(ocr_result, source)
    if ocr_confidence is not None:
        payload["confidence"] = ocr_confidence
    return ExtractionResult(_extract_from_payload(payload), [payload])


def extract_fields_from_images(ocr_results: Iterable[Any]) -> ExtractionResult:
    """Extract independently from each image and retain conflicts across images."""
    payloads = [_ocr_payload(item[1], item[0]) if isinstance(item, tuple) else _ocr_payload(item) for item in ocr_results]
    by_field: dict[str, list[dict[str, Any]]] = {}
    for payload in payloads:
        for field, value in _extract_from_payload(payload).items():
            if value.get("status") == "CONFLICT":
                by_field.setdefault(field, []).extend(value["candidates"])
            else:
                by_field.setdefault(field, []).append(value)
    fields = {}
    for field, candidates in by_field.items():
        distinct = {candidate.get("value") for candidate in candidates}
        fields[field] = candidates[0] if len(distinct) == 1 else {"field": field, "status": "CONFLICT", "candidates": candidates}
    return ExtractionResult(fields, payloads)
