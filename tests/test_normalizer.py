from src.normalizer import normalize_date, normalize_email, normalize_extracted_fields, normalize_field, normalize_mrp, normalize_phone, normalize_quantity, normalize_text


def test_mrp_variants():
    for raw in ("₹120", "Rs. 120", "Rs 120", "MRP: Rs. 120"):
        result = normalize_mrp(raw)
        assert result["normalized_value"]["amount"] == 120.0
        assert result["normalized_value"]["currency"] == "INR"


def test_quantity_variants_and_safe_base_units():
    assert normalize_quantity("500g")["normalized_value"] == {"value": 500.0, "unit": "g", "base_value": 500.0, "base_unit": "g"}
    assert normalize_quantity("5 kg")["normalized_value"]["base_value"] == 5000.0
    assert normalize_quantity("1 L")["normalized_value"]["base_unit"] == "ml"


def test_dates_iso_and_configured_day_first():
    assert normalize_date("2026-08-01")["normalized_value"] == "2026-08-01"
    assert normalize_date("01/08/2026")["normalized_value"] == "2026-08-01"


def test_ambiguous_date_requires_review_when_order_is_unknown():
    result = normalize_date("01/02/2026", date_order=None)
    assert result["normalization_status"] == "NEEDS_REVIEW"
    assert result["normalized_value"] is None


def test_phone_and_email_are_formatting_only():
    phone = normalize_phone("1800-000-0000")
    assert phone["normalized_value"] == "18000000000"
    assert phone["normalization_status"] == "NORMALIZED"
    assert normalize_email(" Support@DemoFoods.com ")["normalized_value"] == "support@demofoods.com"


def test_text_cleanup_preserves_original():
    result = normalize_text("  Demo   Foods Pvt Ltd ")
    assert result["original_value"] == "  Demo   Foods Pvt Ltd "
    assert result["normalized_value"] == "Demo Foods Pvt Ltd"


def test_field_normalization_preserves_extraction_evidence():
    extracted = {"field": "mrp", "value": "Rs. 120", "source_text": "MRP: Rs. 120", "ocr_confidence": 93.4, "image_id": "front", "bbox": [1, 2, 3, 4], "method": "regex", "status": "EXTRACTED"}
    result = normalize_field("mrp", extracted)
    assert result["original_value"] == "Rs. 120"
    assert result["source_text"] == "MRP: Rs. 120"
    assert result["image_id"] == "front"
    assert result["bbox"] == [1, 2, 3, 4]


def test_missing_and_conflict_values_are_preserved():
    missing = normalize_field("mrp", None)
    assert missing["normalization_status"] == "NOT_FOUND"
    conflict = {"status": "CONFLICT", "candidates": [{"value": "₹120"}, {"value": "₹130"}]}
    result = normalize_extracted_fields({"mrp": conflict})["mrp"]
    assert result["normalization_status"] == "CONFLICT"
    assert len(result["candidates"]) == 2

