import json
from pathlib import Path

from src.applicability import APPLICABLE, CONDITIONAL, NEEDS_REVIEW, NOT_APPLICABLE, evaluate_applicability, evaluate_rules_applicability


def rule(condition, rule_id="R-1"):
    return {"rule_id": rule_id, "declaration": "demo", "applicability": condition, "source": "prototype", "notes": "verify"}


def test_all_products_rule():
    result = evaluate_applicability({}, rule({"type": "all_demo_products"}))
    assert result["status"] == APPLICABLE
    assert result["requires_validation"] is True


def test_matching_and_non_matching_category():
    matching = evaluate_applicability({"category": "food"}, rule({"type": "category_in", "values": ["food", "beverage"]}))
    non_matching = evaluate_applicability({"category": "electronics"}, rule({"type": "category_in", "values": ["food", "beverage"]}))
    assert matching["status"] == APPLICABLE
    assert non_matching["status"] == NOT_APPLICABLE
    assert non_matching["requires_validation"] is False


def test_package_type_and_origin_conditions():
    product = {"package_type": "retail", "origin": "domestic"}
    assert evaluate_applicability(product, rule({"type": "package_type_equals", "value": "retail"}))["status"] == APPLICABLE
    assert evaluate_applicability(product, rule({"type": "origin_equals", "value": "domestic"}))["status"] == APPLICABLE


def test_missing_product_information_needs_review():
    result = evaluate_applicability({}, rule({"type": "category_equals", "value": "food"}))
    assert result["status"] == NEEDS_REVIEW
    assert result["requires_review"] is True


def test_conditional_rule():
    result = evaluate_applicability({}, rule({"type": "conditional"}))
    assert result["status"] == CONDITIONAL
    assert result["requires_validation"] is False


def test_unknown_and_malformed_conditions_are_safe():
    assert evaluate_applicability({}, rule({"type": "future_condition"}))["status"] == NEEDS_REVIEW
    assert evaluate_applicability({}, {"rule_id": "R-2"})["status"] == NEEDS_REVIEW
    assert evaluate_applicability({}, None)["status"] == NEEDS_REVIEW


def test_multiple_rules_and_metadata():
    results = evaluate_rules_applicability({"category": "food"}, [rule({"type": "category_in", "values": ["food"]}, "R-1"), rule({"type": "category_in", "values": ["electronics"]}, "R-2")])
    assert [item["status"] for item in results] == [APPLICABLE, NOT_APPLICABLE]
    assert results[0]["rule_id"] == "R-1"
    assert results[0]["source"] == "prototype"


def test_existing_prototype_configuration_loads():
    root = Path(__file__).parents[1]
    products = json.loads((root / "data" / "sample_products.json").read_text(encoding="utf-8"))["products"]
    rules = json.loads((root / "data" / "rules" / "legal_rules.json").read_text(encoding="utf-8"))["rules"]
    results = evaluate_rules_applicability(products[0], rules)
    assert len(results) == len(rules)
    assert all(item["rule_id"] for item in results)

