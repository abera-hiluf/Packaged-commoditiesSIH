from src.rule_engine import validate_fields


def test_missing_required_field_is_non_compliant():
    findings = validate_fields({}, [{"rule_id": "R1", "declaration": "mrp", "required": True, "severity": "HIGH"}])
    assert findings[0]["status"] == "NON-COMPLIANT"


def test_low_ocr_confidence_needs_review():
    fields = {"mrp": {"normalized_value": "Rs 120", "source_text": "MRP ₹120", "ocr_confidence": 20, "extraction_confidence": .4}}
    findings = validate_fields(fields, [{"rule_id": "R1", "declaration": "mrp", "required": True, "severity": "HIGH"}])
    assert findings[0]["status"] == "NEEDS REVIEW"

