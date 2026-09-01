"""Conservative field normalization with original evidence preservation.

Normalization answers what an extracted value represents in a consistent
internal format. It does not validate legal requirements or make compliance
decisions.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any


def _result(field: str, original: Any, normalized: Any, status: str, method: str, warnings: list[str] | None = None, **evidence: Any) -> dict[str, Any]:
    return {"field": field, "original_value": original, "normalized_value": normalized, "normalization_status": status, "normalization_method": method, "warnings": warnings or [], **evidence}


def _raw_value(value: Any) -> tuple[Any, dict[str, Any]]:
    if isinstance(value, dict):
        original = value.get("original_value", value.get("value"))
        evidence = {key: value[key] for key in ("source_text", "ocr_confidence", "extraction_confidence", "image_id", "bbox", "method", "status") if key in value}
        return original, evidence
    return value, {}


def normalize_text(value: Any) -> dict[str, Any]:
    original = value
    if value is None or not str(value).strip():
        return _result("text", original, None, "NOT_FOUND", "text_cleanup")
    normalized = re.sub(r"\s+", " ", str(value).replace("\u00a0", " ")).strip()
    return _result("text", original, normalized, "NORMALIZED", "text_cleanup")


def normalize_mrp(value: Any) -> dict[str, Any]:
    original, evidence = _raw_value(value)
    if original is None or not str(original).strip():
        return _result("mrp", original, None, "NOT_FOUND", "currency_amount_parser", **evidence)
    text = str(original).replace(",", "")
    match = re.search(r"(?i)(?:mrp|max(?:imum)?\s+retail\s+price)?\s*[:\-]?\s*(?:₹|rs\.?|inr)?\s*([0-9]+(?:\.[0-9]{1,2})?)", text)
    if not match:
        return _result("mrp", original, None, "NEEDS_REVIEW", "currency_amount_parser", ["No unambiguous currency amount detected."], **evidence)
    currency = "INR" if re.search(r"₹|rs\.?|inr|mrp|max(?:imum)?\s+retail", text, re.I) else None
    if currency is None:
        return _result("mrp", original, None, "NEEDS_REVIEW", "currency_amount_parser", ["Currency marker was not explicit."], **evidence)
    return _result("mrp", original, {"amount": float(match.group(1)), "currency": currency}, "NORMALIZED", "currency_amount_parser", **evidence)


def normalize_quantity(value: Any) -> dict[str, Any]:
    original, evidence = _raw_value(value)
    if original is None or not str(original).strip():
        return _result("net_quantity", original, None, "NOT_FOUND", "quantity_parser", **evidence)
    match = re.search(r"(?i)([0-9]+(?:\.[0-9]+)?)\s*(kg|kilograms?|g|grams?|ml|millilit(?:re|er)s?|l|lit(?:re|er)s?)\b", str(original).replace(",", ""))
    if not match:
        return _result("net_quantity", original, None, "NEEDS_REVIEW", "quantity_parser", ["No unambiguous numeric value and supported unit detected."], **evidence)
    value_number = float(match.group(1))
    raw_unit = match.group(2).lower()
    unit = "kg" if raw_unit.startswith("kg") or raw_unit.startswith("kil") else "g" if raw_unit.startswith("g") else "ml" if raw_unit.startswith("ml") or raw_unit.startswith("mill") else "L"
    normalized = {"value": value_number, "unit": unit}
    if unit in {"g", "kg"}:
        normalized.update({"base_value": value_number if unit == "g" else value_number * 1000, "base_unit": "g"})
    elif unit in {"ml", "L"}:
        normalized.update({"base_value": value_number if unit == "ml" else value_number * 1000, "base_unit": "ml"})
    return _result("net_quantity", original, normalized, "NORMALIZED", "quantity_parser", **evidence)


def normalize_date(value: Any, date_order: str | None = "DMY") -> dict[str, Any]:
    original, evidence = _raw_value(value)
    if original is None or not str(original).strip():
        return _result("date", original, None, "NOT_FOUND", "date_parser", **evidence)
    text = str(original).strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        try:
            datetime.strptime(text, "%Y-%m-%d")
            return _result("date", original, text, "NORMALIZED", "iso_date_parser", **evidence)
        except ValueError:
            pass
    match = re.fullmatch(r"(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4})", text)
    if match and date_order is None and int(match.group(1)) <= 12 and int(match.group(2)) <= 12:
        return _result("date", original, None, "NEEDS_REVIEW", "date_parser", ["Numeric date order is ambiguous."], **evidence)
    formats = ["%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%m/%Y", "%b %Y", "%B %Y"]
    for fmt in formats:
        try:
            parsed = datetime.strptime(text, fmt)
            return _result("date", original, parsed.strftime("%Y-%m-%d"), "NORMALIZED", "date_parser", **evidence)
        except ValueError:
            continue
    return _result("date", original, None, "NEEDS_REVIEW", "date_parser", ["Date format or value could not be interpreted safely."], **evidence)


def normalize_phone(value: Any) -> dict[str, Any]:
    original, evidence = _raw_value(value)
    if original is None or not str(original).strip():
        return _result("consumer_care", original, None, "NOT_FOUND", "phone_parser", **evidence)
    digits = re.sub(r"\D", "", str(original))
    if len(digits) < 10 or len(digits) > 13:
        return _result("consumer_care", original, None, "NEEDS_REVIEW", "phone_parser", ["Phone-like value has an unexpected digit count; existence and validity are not checked."], **evidence)
    return _result("consumer_care", original, digits, "NORMALIZED", "phone_parser", ["Formatting normalized only; number validity was not checked."], **evidence)


def normalize_email(value: Any) -> dict[str, Any]:
    original, evidence = _raw_value(value)
    if original is None or not str(original).strip():
        return _result("email", original, None, "NOT_FOUND", "email_parser", **evidence)
    normalized = re.sub(r"\s+", "", str(original)).lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", normalized):
        return _result("email", original, None, "NEEDS_REVIEW", "email_parser", ["Email-like format is ambiguous; existence was not checked."], **evidence)
    return _result("email", original, normalized, "NORMALIZED", "email_parser", ["Formatting normalized only; address existence was not checked."], **evidence)


def normalize_field(field_name: str, value: Any) -> dict[str, Any]:
    """Normalize one extracted field while retaining evidence metadata."""
    if field_name == "mrp":
        return normalize_mrp(value)
    if field_name == "net_quantity":
        return normalize_quantity(value)
    if field_name in {"manufacture_date", "packing_date", "import_date", "best_before", "use_by"}:
        result = normalize_date(value)
        result["field"] = field_name
        return result
    if field_name == "consumer_care":
        return normalize_phone(value)
    if field_name == "email":
        return normalize_email(value)
    original, evidence = _raw_value(value)
    result = normalize_text(original)
    result["field"] = field_name
    result.update(evidence)
    return result


def normalize_extracted_fields(extracted_fields: dict[str, Any]) -> dict[str, Any]:
    """Normalize a flat extractor field mapping without dropping provenance."""
    normalized = {}
    for field, value in extracted_fields.items():
        if isinstance(value, dict) and value.get("status") == "CONFLICT":
            candidates = [normalize_field(field, candidate) for candidate in value.get("candidates", [])]
            normalized[field] = {"field": field, "original_value": None, "normalized_value": None, "normalization_status": "CONFLICT", "normalization_method": "conflict_preserved", "warnings": ["Multiple extracted candidates were preserved for human review."], "candidates": candidates}
        else:
            normalized[field] = normalize_field(field, value)
    return normalized

