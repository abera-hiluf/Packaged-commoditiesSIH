from src.extractor import extract_fields, extract_fields_from_images


def ocr(text, image_id=None, confidence=91.0, lines=None):
    return {"text": text, "confidence": confidence, "lines": lines or [], "words": [], "image_id": image_id}


def test_mrp_and_quantity_extraction():
    fields = extract_fields(ocr("MRP: ₹120\nNet Quantity: 500 g"))
    assert fields["mrp"]["value"] == "₹120"
    assert fields["net_quantity"]["value"] == "500 g"
    assert fields["mrp"]["status"] == "EXTRACTED"


def test_manufacturer_consumer_care_and_product_name():
    fields = extract_fields(ocr("Product Name: Premium Rice\nManufactured by: Sunvale Foods Pvt Ltd\nCustomer Care: 1800-000-0000"))
    assert fields["commodity_name"]["value"] == "Premium Rice"
    assert "Sunvale Foods" in fields["manufacturer"]["value"]
    assert "1800" in fields["consumer_care"]["value"]


def test_dates_origin_best_before_and_unit_price():
    fields = extract_fields(ocr("MFD: 08/2026\nCountry of Origin: India\nBest Before: 12 months\nUnit Sale Price: ₹40 per kg"))
    assert fields["manufacture_date"]["value"] == "08/2026"
    assert fields["country_of_origin"]["value"] == "India"
    assert fields["best_before"]["value"] == "12 months"
    assert fields["unit_sale_price"]["value"] == "₹40 per kg"


def test_missing_fields_are_not_compliance_decisions():
    fields = extract_fields(ocr("Premium Rice"))
    assert "mrp" not in fields
    assert all(value.get("status") not in {"COMPLIANT", "NON-COMPLIANT"} for value in fields.values())


def test_ambiguous_mrp_is_not_over_extracted():
    fields = extract_fields(ocr("MRP subject to change"))
    assert "mrp" not in fields


def test_evidence_preserves_ocr_confidence_image_and_bbox():
    lines = [{"text": "MRP: ₹120", "confidence": 88, "x": 10, "y": 20, "width": 90, "height": 18}]
    field = extract_fields(ocr("MRP: ₹120", "front", 88, lines))["mrp"]
    assert field["ocr_confidence"] == 88
    assert field["image_id"] == "front"
    assert field["bbox"] == [10, 20, 90, 18]
    assert field["method"] == "regex"


def test_multiple_images_preserve_source():
    result = extract_fields_from_images([("front", ocr("MRP: ₹120")), ("back", ocr("Manufactured by: Demo Foods"))])
    assert result["mrp"]["image_id"] == "front"
    assert result["manufacturer"]["image_id"] == "back"


def test_conflicting_values_are_explicit():
    result = extract_fields_from_images([("front", ocr("MRP: ₹120")), ("back", ocr("MRP: ₹130"))])
    assert result["mrp"]["status"] == "CONFLICT"
    assert {candidate["value"] for candidate in result["mrp"]["candidates"]} == {"₹120", "₹130"}

