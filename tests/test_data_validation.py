import json
from pathlib import Path

ROOT = Path(__file__).parents[1]

def load(relative: str):
    with (ROOT / relative).open(encoding="utf-8") as handle:
        return json.load(handle)

def test_step_two_json_files_are_valid():
    products = load("data/sample_products.json")
    inspections = load("data/inspections.json")
    rules = load("data/rules/legal_rules.json")
    assert products["metadata"]["not_official_data"] is True
    assert inspections["metadata"]["not_official_data"] is True
    assert rules["metadata"]["not_authoritative"] is True

def test_product_and_inspection_references_are_valid():
    products = load("data/sample_products.json")["products"]
    ids = {product["product_id"] for product in products}
    assert len(products) >= 6
    assert len(ids) == len(products)
    assert all(product["inspection_id"] and product["image_paths"] for product in products)
    assert all(item["product_id"] in ids for item in load("data/inspections.json")["inspections"])

def test_rule_ids_and_required_schema_are_valid():
    rules = load("data/rules/legal_rules.json")["rules"]
    ids = [rule["rule_id"] for rule in rules]
    required = {"rule_id", "declaration", "description", "required", "applicability", "validation_type", "validation_parameters", "severity", "effective_from", "effective_to", "source", "notes"}
    assert len(ids) == len(set(ids))
    assert {rule["validation_type"] for rule in rules} >= {"presence", "quantity", "price", "date", "contact", "readability", "conditional"}
    assert all(required <= rule.keys() for rule in rules)

