"""Explainable declaration extraction from OCR text."""

import re
from typing import Any

from .normalizer import normalize_field

FIELD_PATTERNS = {
    "mrp": [r"(?:mrp|maximum retail price)\s*(?:rs\.?|₹)?\s*([0-9]+(?:\.[0-9]{1,2})?)"],
    "net_quantity": [r"(?:net\s*(?:qty|quantity|wt|weight))\s*[:\-]?\s*([0-9.,]+\s*(?:kg|kgs?|g|gm|gms?|ml|l|litres?|liters?))"],
    "consumer_care": [r"(?:consumer|customer)\s*care\s*[:\-]?\s*([^\n]+)", r"(?:helpline|toll\s*free)\s*[:\-]?\s*([^\n]+)"],
    "manufacturer": [r"(?:manufactured|manufactured\s*by|mfd\s*by)\s*[:\-]?\s*([^\n]+)"],
    "packer": [r"(?:packed|packed\s*by)\s*[:\-]?\s*([^\n]+)"],
    "importer": [r"(?:imported|importer)\s*[:\-]?\s*([^\n]+)"],
    "country_of_origin": [r"(?:country\s*of\s*origin|made\s*in)\s*[:\-]?\s*([^\n]+)"],
    "manufacture_date": [r"(?:mfg|manufactur(?:e|ed)|packed\s*on)\s*(?:date)?\s*[:\-]?\s*([0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{2,4}|[A-Za-z]+\s*[0-9]{4})"],
    "best_before": [r"best\s*before\s*[:\-]?\s*([^\n]+)"],
    "use_by": [r"use\s*by\s*[:\-]?\s*([^\n]+)"],
    "unit_sale_price": [r"(?:unit\s*sale\s*price|price\s*per)\s*[:\-]?\s*([^\n]+)"],
}


def extract_fields(text: str, ocr_confidence: float | None = None, source: str = "OCR") -> dict[str, dict[str, Any]]:
    fields: dict[str, dict[str, Any]] = {}
    for field, patterns in FIELD_PATTERNS.items():
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                original = match.group(1).strip()
                fields[field] = {"field": field, "original_value": original, "normalized_value": normalize_field(field, original), "source_text": match.group(0).strip(), "source": source, "ocr_confidence": ocr_confidence, "extraction_confidence": 0.85 if ocr_confidence is None else min(0.98, 0.55 + ocr_confidence / 200), "status": "EXTRACTED"}
                break
    if not any(k in fields for k in ("commodity_name",)):
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if lines:
            fields["commodity_name"] = {"field": "commodity_name", "original_value": lines[0], "normalized_value": normalize_field("commodity_name", lines[0]), "source_text": lines[0], "source": source, "ocr_confidence": ocr_confidence, "extraction_confidence": 0.45, "status": "EXTRACTED"}
    return fields

