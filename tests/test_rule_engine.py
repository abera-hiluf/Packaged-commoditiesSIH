from src.applicability import APPLICABLE, NOT_APPLICABLE
from src.rule_engine import FAIL, NEEDS_REVIEW, NOT_APPLICABLE as ENGINE_NOT_APPLICABLE, PASS, evaluate_all_rules, evaluate_rule, overall_product_status, summarize_findings


def rule(field="mrp", kind="price", required=True, rule_id="R1"):
    return {"rule_id": rule_id, "declaration": field, "validation_type": kind, "required": required, "severity": "HIGH", "source": "prototype", "notes": "verify"}


def field(value, original="MRP: ₹120", **extra):
    return {"field": "mrp", "original_value": original, "normalized_value": value, "status": "EXTRACTED", "ocr_confidence": 92, "extraction_confidence": .9, "source_text": original, **extra}


def applicable(rule_id="R1"):
    return {"rule_id": rule_id, "status": APPLICABLE, "reason": "configured"}


def test_valid_price_passes_and_preserves_evidence():
    result = evaluate_rule(rule(), {"mrp": field({"amount": 120.0, "currency": "INR"})}, applicable())
    assert result["status"] == PASS
    assert result["field_value"]["amount"] == 120.0
    assert result["evidence"]["source_text"] == "MRP: ₹120"


def test_missing_required_field_requires_review():
    result = evaluate_rule(rule(), {}, applicable())
    assert result["status"] == NEEDS_REVIEW
    assert result["field_value"] is None


def test_non_applicable_rule_is_not_evaluated():
    result = evaluate_rule(rule(), {}, {"rule_id": "R1", "status": NOT_APPLICABLE, "reason": "category mismatch"})
    assert result["status"] == ENGINE_NOT_APPLICABLE


def test_conflict_and_ambiguous_values_require_review():
    conflict = {"field": "mrp", "status": "CONFLICT", "candidates": [{"value": "₹120"}, {"value": "₹130"}]}
    assert evaluate_rule(rule(), {"mrp": conflict}, applicable())["status"] == NEEDS_REVIEW
    ambiguous = field({"amount": 120.0, "currency": "INR"}, status="AMBIGUOUS")
    assert evaluate_rule(rule(), {"mrp": ambiguous}, applicable())["status"] == NEEDS_REVIEW


def test_quantity_and_contact_validation():
    quantity = evaluate_rule(rule("net_quantity", "quantity"), {"net_quantity": field({"value": 500.0, "unit": "g"})}, applicable())
    contact = evaluate_rule(rule("consumer_care", "contact"), {"consumer_care": field("18000000000")}, applicable())
    assert quantity["status"] == PASS
    assert contact["status"] == PASS


def test_low_ocr_confidence_requires_review():
    low = field({"amount": 120.0, "currency": "INR"}, ocr_confidence=20)
    assert evaluate_rule(rule(), {"mrp": low}, applicable())["status"] == NEEDS_REVIEW


def test_multiple_rules_summary_and_overall_status():
    rules = [rule(rule_id="R1"), rule("net_quantity", "quantity", rule_id="R2")]
    fields = {"mrp": field({"amount": 120.0, "currency": "INR"})}
    results = evaluate_all_rules(rules, fields, [applicable("R1"), applicable("R2")])
    summary = summarize_findings(results)
    assert summary["total_rules"] == 2
    assert summary["passed"] == 1 and summary["needs_review"] == 1
    assert overall_product_status(results) == "REVIEW_REQUIRED"


def test_warnings_do_not_automatically_fail_product():
    result = evaluate_rule(rule("country_of_origin", "conditional", required=False), {}, applicable())
    assert result["status"] == "WARNING"
    assert overall_product_status([result]) == "COMPLIANT"
