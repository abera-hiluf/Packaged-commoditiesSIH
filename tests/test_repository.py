import pytest

from src.repository import Repository


def setup_repository(tmp_path):
    return Repository(tmp_path / "compliance.db")


def seed(repository):
    repository.create_product({"product_id": "P-1", "product_name": "Demo", "category": "Food", "manufacturer": "Demo Co"})
    repository.create_inspection({"inspection_id": "I-1", "product_id": "P-1", "overall_status": "REVIEW_REQUIRED"})


def test_product_and_inspection_round_trip(tmp_path):
    repository = setup_repository(tmp_path)
    seed(repository)
    assert repository.get_product("P-1")["product_name"] == "Demo"
    assert repository.get_inspection("I-1")["product_id"] == "P-1"
    assert len(repository.list_products()) == 1
    assert len(repository.list_inspections("Demo")) == 1


def test_related_records_and_json_round_trip(tmp_path):
    repository = setup_repository(tmp_path)
    seed(repository)
    repository.save_image({"image_id": "front", "inspection_id": "I-1", "image_path": "samples/front.png", "image_type": "front"})
    repository.save_ocr_result({"image_id": "front", "text": "MRP: ₹120", "confidence": 92.0, "engine": "tesseract", "words": [{"text": "MRP"}], "lines": []})
    repository.save_extracted_field("I-1", {"field": "mrp", "original_value": "₹120", "status": "EXTRACTED", "extraction_confidence": .9, "image_id": "front", "source_text": "MRP: ₹120", "bbox": [1, 2, 3, 4], "method": "regex"})
    repository.save_normalized_field("I-1", {"field": "mrp", "normalized_value": {"amount": 120.0, "currency": "INR"}, "normalization_status": "NORMALIZED", "normalization_method": "currency"})
    repository.save_applicability_result("I-1", {"rule_id": "R1", "status": "APPLICABLE", "reason": "demo"})
    repository.save_compliance_finding("I-1", {"finding_id": "F-1", "rule_id": "R1", "declaration": "mrp", "status": "PASS", "severity": "HIGH", "message": "pass", "reason": "detected", "field_value": {"amount": 120.0}, "evidence_ids": ["EV-1"]})
    repository.save_evidence({"evidence_id": "EV-1", "image_id": "front", "image_path": "samples/front.png", "source_text": "MRP: ₹120", "bbox": [1, 2, 3, 4], "ocr_confidence": 92.0, "extraction_confidence": .9, "field": "mrp", "original_value": "₹120", "normalized_value": {"amount": 120.0}, "extraction_method": "regex"}, "F-1")
    findings = repository.get_findings_for_inspection("I-1")
    evidence = repository.get_evidence_for_finding("F-1")
    assert findings[0]["field_value"]["amount"] == 120.0
    assert evidence[0]["bbox"] == [1, 2, 3, 4]
    assert evidence[0]["normalized_value"]["amount"] == 120.0


def test_review_preserves_original_evidence(tmp_path):
    repository = setup_repository(tmp_path)
    seed(repository)
    repository.save_compliance_finding("I-1", {"finding_id": "F-1", "status": "PASS"})
    repository.save_evidence({"evidence_id": "EV-1", "source_text": "MRP: ₹120", "original_value": "₹120"}, "F-1")
    repository.update_review_status("F-1", "CORRECTED", "Reviewer", "₹125", "Checked against artwork")
    evidence = repository.get_evidence_for_finding("F-1")[0]
    assert evidence["original_value"] == "₹120"


def test_duplicate_and_foreign_key_errors(tmp_path):
    repository = setup_repository(tmp_path)
    repository.create_product({"product_id": "P-1"})
    with pytest.raises(Exception):
        repository.create_product({"product_id": "P-1"})
    with pytest.raises(Exception):
        repository.create_inspection({"inspection_id": "I-bad", "product_id": "missing"})


def test_empty_queries_and_metrics(tmp_path):
    repository = setup_repository(tmp_path)
    assert repository.get_product("missing") is None
    assert repository.get_inspection("missing") is None
    assert repository.list_recent_inspections() == []
    assert repository.metrics()["total_products"] == 0

