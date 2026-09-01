"""Configuration-driven rule applicability decisions.

Applicability answers whether a configured rule should be considered. It does
not validate field values and does not produce compliance statuses.
"""

from __future__ import annotations

from typing import Any, Iterable

APPLICABLE = "APPLICABLE"
NOT_APPLICABLE = "NOT_APPLICABLE"
CONDITIONAL = "CONDITIONAL"
NEEDS_REVIEW = "NEEDS_REVIEW"


def _result(rule: dict[str, Any], status: str, reason: str, requires_validation: bool = False, requires_review: bool = False, error: str | None = None) -> dict[str, Any]:
    """Build a stable result while preserving relevant rule metadata."""
    output = {
        "rule_id": rule.get("rule_id"),
        "declaration": rule.get("declaration"),
        "status": status,
        "reason": reason,
        "requires_validation": requires_validation,
        "requires_review": requires_review,
        "source": rule.get("source"),
        "effective_from": rule.get("effective_from"),
        "effective_to": rule.get("effective_to"),
        "notes": rule.get("notes"),
    }
    if error:
        output["error"] = error
    return output


def evaluate_applicability(product: dict[str, Any] | None, rule: dict[str, Any] | None) -> dict[str, Any]:
    """Evaluate one configured applicability condition without validating values."""
    product = product or {}
    rule = rule or {}
    if not rule.get("rule_id"):
        return _result(rule, NEEDS_REVIEW, "Needs review because the rule has no rule ID.", requires_review=True, error="missing_rule_id")
    condition = rule.get("applicability")
    if not isinstance(condition, dict) or not condition.get("type"):
        return _result(rule, NEEDS_REVIEW, "Needs review because applicability configuration is missing or malformed.", requires_review=True, error="missing_applicability_configuration")

    condition_type = str(condition["type"]).lower()
    if condition_type in {"all", "all_products", "all_demo_products"}:
        return _result(rule, APPLICABLE, "Rule applies to all products covered by this configured prototype.", requires_validation=True)
    if condition_type in {"conditional", "manual_review", "manual"}:
        return _result(rule, CONDITIONAL, "Applicability depends on a condition that requires human review.", requires_review=True)
    if condition_type in {"category_equals", "package_type_equals", "origin_equals"}:
        field = condition_type.removesuffix("_equals")
        expected = condition.get("value")
        actual = product.get(field)
        if actual is None or actual == "":
            return _result(rule, NEEDS_REVIEW, f"Needs review because product {field} is unavailable.", requires_review=True)
        if expected is None:
            return _result(rule, NEEDS_REVIEW, f"Needs review because the configured {field} condition is incomplete.", requires_review=True, error="missing_condition_value")
        status = APPLICABLE if str(actual).casefold() == str(expected).casefold() else NOT_APPLICABLE
        reason = f"Rule applies because product {field} matches the configured condition." if status == APPLICABLE else f"Rule does not apply because product {field} does not match the configured condition."
        return _result(rule, status, reason, requires_validation=status == APPLICABLE)
    if condition_type in {"category_in", "origin_in"}:
        field = condition_type.removesuffix("_in")
        actual = product.get(field)
        values = condition.get("values")
        if actual is None or actual == "":
            return _result(rule, NEEDS_REVIEW, f"Needs review because product {field} is unavailable.", requires_review=True)
        if not isinstance(values, list) or not values:
            return _result(rule, NEEDS_REVIEW, f"Needs review because the configured {field} values are missing.", requires_review=True, error="missing_condition_values")
        matches = {str(value).casefold() for value in values}
        status = APPLICABLE if str(actual).casefold() in matches else NOT_APPLICABLE
        reason = f"Rule applies because product {field} matches the configured list." if status == APPLICABLE else f"Rule does not apply because product {field} is outside the configured list."
        return _result(rule, status, reason, requires_validation=status == APPLICABLE)
    if condition_type in {"field_present", "field_absent"}:
        field = condition.get("field")
        if not field:
            return _result(rule, NEEDS_REVIEW, "Needs review because the configured field condition is incomplete.", requires_review=True, error="missing_condition_field")
        present = product.get(field) not in (None, "", [], {})
        is_applicable = present if condition_type == "field_present" else not present
        status = APPLICABLE if is_applicable else NOT_APPLICABLE
        return _result(rule, status, f"Rule applicability evaluated from whether product field '{field}' is present.", requires_validation=is_applicable)
    return _result(rule, NEEDS_REVIEW, f"Needs review because applicability type '{condition_type}' is not supported.", requires_review=True, error="unknown_applicability_type")


def evaluate_rules_applicability(product: dict[str, Any] | None, rules: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Evaluate multiple rules independently, retaining rule metadata."""
    results = []
    for rule in rules or []:
        if not isinstance(rule, dict):
            results.append({"rule_id": None, "status": NEEDS_REVIEW, "reason": "Needs review because the rule definition is malformed.", "requires_validation": False, "requires_review": True, "error": "malformed_rule"})
        else:
            results.append(evaluate_applicability(product, rule))
    return results

