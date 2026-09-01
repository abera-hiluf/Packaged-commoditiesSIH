"""Data-driven prototype rule evaluation."""

import json
from pathlib import Path
from typing import Any


def load_rules(path: str | Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def validate_fields(fields: dict[str, dict[str, Any]], rules: list[dict[str, Any]], context: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    findings = []
    for rule in rules:
        field = rule.get("declaration")
        value = fields.get(field)
        if rule.get("required", False) and not value:
            status = "NON-COMPLIANT"
            reason = "Required declaration was not detected in the supplied evidence."
        elif not value:
            status = "NEEDS REVIEW"
            reason = "Applicability or presence could not be established from the available evidence."
        elif value.get("ocr_confidence") is not None and value["ocr_confidence"] < 60:
            status = "NEEDS REVIEW"
            reason = "The declaration was extracted, but OCR confidence is low."
        else:
            status = "COMPLIANT"
            reason = "Declaration detected; verify applicability and visual legibility during human review."
        findings.append({"field": field, "status": status, "value": value.get("normalized_value") if value else None, "rule_id": rule.get("rule_id"), "severity": rule.get("severity", "MEDIUM"), "reason": reason, "evidence": value.get("source_text") if value else None, "ocr_confidence": value.get("ocr_confidence") if value else None, "extraction_confidence": value.get("extraction_confidence") if value else None, "rule_description": rule.get("description", ""), "reviewer_status": None})
    return findings

