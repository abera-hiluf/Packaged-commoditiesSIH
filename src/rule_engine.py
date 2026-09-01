"""Deterministic validation of normalized fields against configured rules.

This module consumes applicability decisions and never evaluates a rule that is
not marked APPLICABLE. Prototype rule configuration is not authoritative law.
"""

from __future__ import annotations

import re
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from .applicability import APPLICABLE, NOT_APPLICABLE

PASS = "PASS"
FAIL = "FAIL"
WARNING = "WARNING"
NEEDS_REVIEW = "NEEDS_REVIEW"


def load_rules(path: str | Path) -> dict[str, Any]:
    """Load externally configured prototype rules without embedding legal logic."""
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _evidence(field: dict[str, Any] | None) -> dict[str, Any] | list[dict[str, Any]] | None:
    if not field:
        return None
    if field.get("status") == "CONFLICT":
        return field.get("candidates", [])
    return {key: field.get(key) for key in ("source_text", "image_id", "bbox", "ocr_confidence", "extraction_confidence", "original_value", "normalized_value") if key in field}


def _finding(rule: dict[str, Any], status: str, message: str, reason: str, field: dict[str, Any] | None = None, requires_review: bool = False) -> dict[str, Any]:
    return {"rule_id": rule.get("rule_id"), "declaration": rule.get("declaration"), "status": status, "severity": rule.get("severity"), "message": message, "reason": reason, "field_value": field.get("normalized_value") if field and field.get("status") != "CONFLICT" else None, "evidence": _evidence(field), "requires_review": requires_review, "rule_source": rule.get("source"), "rule_notes": rule.get("notes")}


def _validate_value(validation_type: str, field: dict[str, Any], parameters: dict[str, Any]) -> tuple[str, str, str, bool]:
    if field.get("status") in {"CONFLICT", "AMBIGUOUS"} or field.get("normalization_status") in {"CONFLICT", "NEEDS_REVIEW"}:
        return NEEDS_REVIEW, "Field requires manual verification.", "Ambiguous or conflicting field evidence was preserved.", True
    if field.get("ocr_confidence") is not None and field["ocr_confidence"] < 60:
        return NEEDS_REVIEW, "Field requires manual verification.", "OCR confidence is low; verify the value against the original package image.", True
    value = field.get("normalized_value")
    if value is None:
        return FAIL, "Configured field value is not usable.", "The field was detected but no normalized value is available.", False
    if validation_type == "presence":
        return PASS, "Configured declaration was detected.", "An applicable field was extracted and contains a value.", False
    if validation_type == "price":
        valid = isinstance(value, dict) and isinstance(value.get("amount"), (int, float)) and value.get("amount") >= 0 and bool(value.get("currency"))
        return (PASS, "Price has a recognizable amount and currency.", "The normalized price structure contains a numeric amount and currency.", False) if valid else (FAIL, "Price representation could not be validated.", "The configured price check did not find a numeric amount and currency.", False)
    if validation_type == "quantity":
        valid = isinstance(value, dict) and isinstance(value.get("value"), (int, float)) and value.get("value") > 0 and bool(value.get("unit"))
        return (PASS, "Quantity has a recognizable value and unit.", "The normalized quantity structure contains a numeric value and unit.", False) if valid else (FAIL, "Quantity representation could not be validated.", "The configured quantity check did not find a usable numeric value and unit.", False)
    if validation_type == "date":
        try:
            datetime.strptime(str(value), "%Y-%m-%d")
            return PASS, "Date has a parseable normalized representation.", "The normalized date uses the expected ISO representation.", False
        except ValueError:
            return FAIL, "Date representation could not be validated.", "The configured date check could not parse the normalized value.", False
    if validation_type == "contact":
        text = str(value)
        recognizable = bool(re.search(r"\d{7,}", text) or re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", text) or re.match(r"https?://", text))
        return (PASS, "Consumer-care contact has a recognizable format.", "The contact resembles a phone number, email, or website; operation was not tested.", False) if recognizable else (FAIL, "Consumer-care contact format could not be validated.", "No recognizable phone, email, or website pattern was found.", False)
    if validation_type == "basic_format":
        pattern = parameters.get("pattern")
        if pattern:
            try:
                valid = bool(re.fullmatch(pattern, str(value)))
            except re.error:
                return NEEDS_REVIEW, "Configured format requires manual review.", "The prototype rule contains an invalid format pattern.", True
            return (PASS, "Value matches the configured basic format.", "The normalized value matched the configured pattern.", False) if valid else (FAIL, "Value does not match the configured basic format.", "The normalized value did not match the configured pattern.", False)
        return WARNING, "Basic format check is limited.", "No format pattern was configured; human review is recommended.", True
    if validation_type in {"conditional", "readability"}:
        return NEEDS_REVIEW, "Field requires manual verification.", "This prototype validation depends on information not reliably available to the rule engine.", True
    return NEEDS_REVIEW, "Validation type requires manual review.", f"Validation type '{validation_type}' is not supported by this prototype.", True


def evaluate_rule(rule: dict[str, Any], normalized_fields: dict[str, Any], applicability_result: dict[str, Any]) -> dict[str, Any]:
    """Evaluate one rule only when applicability has marked it APPLICABLE."""
    if applicability_result.get("status") == NOT_APPLICABLE:
        return _finding(rule, NOT_APPLICABLE, "Rule is not applicable to this product.", applicability_result.get("reason", "Applicability engine excluded this rule."))
    if applicability_result.get("status") != APPLICABLE:
        return _finding(rule, NEEDS_REVIEW, "Rule applicability requires manual review.", applicability_result.get("reason", "Applicability was not established."), requires_review=True)
    field_name = rule.get("declaration")
    field = normalized_fields.get(field_name)
    if not field:
        if rule.get("required"):
            return _finding(rule, FAIL, f"Required {field_name} declaration was not detected.", "The applicable field was not extracted from the available package evidence.")
        return _finding(rule, WARNING, f"Optional or conditional {field_name} declaration was not detected.", "The field is not configured as required; applicability or presence may need human review.", requires_review=True)
    if field.get("status") == "CONFLICT":
        return _finding(rule, NEEDS_REVIEW, f"{field_name} requires manual verification.", f"Multiple conflicting {field_name} values were detected across package evidence.", field, True)
    if field.get("normalization_status") == "NOT_FOUND":
        return _finding(rule, FAIL if rule.get("required") else WARNING, f"{field_name} was not normalized.", "The applicable field did not produce a normalized value.", field)
    status, message, reason, review = _validate_value(rule.get("validation_type", "presence"), field, rule.get("validation_parameters", {}))
    return _finding(rule, status, message, reason, field, review)


def evaluate_all_rules(rules: Iterable[dict[str, Any]], normalized_fields: dict[str, Any], applicability_results: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Evaluate configured rules matched by rule ID to applicability results."""
    applicability_by_id = {item.get("rule_id"): item for item in applicability_results or []}
    return [evaluate_rule(rule, normalized_fields or {}, applicability_by_id.get(rule.get("rule_id"), {"status": "NEEDS_REVIEW", "reason": "No applicability result was supplied."})) for rule in rules or []]


def summarize_findings(findings: Iterable[dict[str, Any]]) -> dict[str, int]:
    findings = list(findings)
    return {"total_rules": len(findings), "passed": sum(f.get("status") == PASS for f in findings), "failed": sum(f.get("status") == FAIL for f in findings), "warnings": sum(f.get("status") == WARNING for f in findings), "needs_review": sum(f.get("status") == NEEDS_REVIEW for f in findings), "not_applicable": sum(f.get("status") == NOT_APPLICABLE for f in findings)}


def overall_product_status(findings: Iterable[dict[str, Any]]) -> str:
    findings = list(findings)
    applicable = [f for f in findings if f.get("status") != NOT_APPLICABLE]
    if any(f.get("status") == NEEDS_REVIEW for f in applicable):
        return "REVIEW_REQUIRED"
    if any(f.get("status") == FAIL for f in applicable):
        return "NON_COMPLIANT"
    return "COMPLIANT"


def validate_fields(fields: dict[str, Any], rules: list[dict[str, Any]], context: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Compatibility adapter for the earlier app API; new callers should use the Step 8 APIs."""
    from .applicability import evaluate_rules_applicability
    findings = evaluate_all_rules(rules, fields, evaluate_rules_applicability(context or {}, rules))
    legacy = {PASS: "COMPLIANT", FAIL: "NON-COMPLIANT", NEEDS_REVIEW: "NEEDS REVIEW", WARNING: "WARNING", NOT_APPLICABLE: "NOT APPLICABLE"}
    for finding in findings:
        finding["status"] = legacy.get(finding["status"], finding["status"])
    return findings
