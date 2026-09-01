from src.evidence import EvidenceStore, apply_reviewer_correction, attach_evidence_to_finding, create_field_evidence, validate_evidence


def extracted(value="₹120", image_id="front"):
    return {"field": "mrp", "value": value, "original_value": value, "source_text": f"MRP: {value}", "ocr_confidence": 93.4, "extraction_confidence": .95, "image_id": image_id, "bbox": [100, 200, 180, 225], "method": "regex"}


def normalized(value={"amount": 120.0, "currency": "INR"}):
    return {"field": "mrp", "original_value": "₹120", "normalized_value": value, "normalization_status": "NORMALIZED", "normalization_method": "currency_amount_parser"}


def test_evidence_creation_preserves_provenance():
    record = create_field_evidence(extracted(), normalized(), "samples/package_images/demo_p001_complete.png")
    assert record["evidence_id"].startswith("EV-")
    assert record["source_text"] == "MRP: ₹120"
    assert record["bbox"] == [100, 200, 180, 225]
    assert record["ocr_confidence"] == 93.4
    assert record["extraction_confidence"] == .95
    assert record["normalized_value"]["amount"] == 120.0


def test_store_retrieval_and_unique_ids():
    store = EvidenceStore()
    first = create_field_evidence(extracted("₹120"), normalized())
    second = create_field_evidence(extracted("₹130", "back"), normalized({"amount": 130.0, "currency": "INR"}))
    first_id, second_id = store.add_evidence(first), store.add_evidence(second)
    assert first_id != second_id
    assert store.get_evidence(first_id)["image_id"] == "front"
    assert len(store.list_evidence()) == 2


def test_finding_linking_and_multiple_evidence():
    store = EvidenceStore()
    ids = [store.add_evidence(create_field_evidence(extracted(value, image), normalized({"amount": amount, "currency": "INR"}))) for value, image, amount in (("₹120", "front", 120), ("₹130", "back", 130))]
    finding = attach_evidence_to_finding({"rule_id": "R1", "status": "NEEDS_REVIEW"}, [store.get_evidence(ids[0]), store.get_evidence(ids[1])])
    saved = store.attach_finding(finding)
    assert len(saved["evidence_ids"]) == 2
    assert len(store.get_evidence_for_finding(saved["finding_id"])) == 2


def test_missing_evidence_is_explicit_but_allowed():
    finding = attach_evidence_to_finding({"rule_id": "R1", "status": "FAIL"}, None)
    assert finding["evidence_ids"] == []
    assert finding["evidence_status"] == "NO_SUPPORTING_TEXT_DETECTED"


def test_reference_validation_detects_errors():
    store = EvidenceStore()
    valid = create_field_evidence(extracted(), normalized())
    store.add_evidence(valid)
    store.attach_finding({"finding_id": "F-1", "status": "PASS"}, [valid["evidence_id"]])
    assert store.validate_references() == []
    assert "Evidence record is missing evidence_id" in validate_evidence([{"field": "mrp", "original_value": "x", "source_text": ""}])


def test_reviewer_correction_does_not_overwrite_original():
    record = create_field_evidence(extracted(), normalized())
    corrected = apply_reviewer_correction(record, "₹125", "Reviewer A", "Verified against artwork")
    assert corrected["original_value"] == "₹120"
    assert corrected["reviewer_value"] == "₹125"
    assert corrected["review_status"] == "CORRECTED"

