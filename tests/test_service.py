from pathlib import Path

from src.service import process_inspection


def fake_pipeline(monkeypatch, tmp_path):
    class Prepared(dict):
        pass
    monkeypatch.setattr("src.service.preprocess_image", lambda path: {"processed": "processed", "metadata": {"original_width": 10}})
    monkeypatch.setattr("src.service.run_ocr", lambda image: {"text": "MRP: ₹120\nNet Quantity: 500 g", "confidence": 92, "words": [], "lines": [], "engine": "mock", "error": None})
    monkeypatch.setattr("src.service.extract_fields_from_images", lambda items: type("Fields", (), {"fields": {"mrp": {"field": "mrp", "value": "₹120", "original_value": "₹120", "source_text": "MRP: ₹120", "image_id": "front", "status": "EXTRACTED", "ocr_confidence": 92, "extraction_confidence": .9, "method": "mock"}},})())
    monkeypatch.setattr("src.service.normalize_extracted_fields", lambda fields: {"mrp": {"field": "mrp", "original_value": "₹120", "normalized_value": {"amount": 120.0, "currency": "INR"}, "normalization_status": "NORMALIZED"}})


def test_service_orchestrates_and_returns_structured_result(monkeypatch, tmp_path):
    fake_pipeline(monkeypatch, tmp_path)
    product = {"product_id": "P1", "product_name": "Demo", "category": "food"}
    rules = [{"rule_id": "R1", "declaration": "mrp", "required": True, "validation_type": "price", "severity": "HIGH", "applicability": {"type": "all_demo_products"}}]
    result = process_inspection(product, ["front.png"], rules)
    assert result["status"] == "COMPLETED"
    assert result["inspection_id"].startswith("INSP-")
    assert result["findings"][0]["status"] == "PASS"
    assert result["findings"][0]["evidence_ids"]
    assert result["evidence"][0]["source_text"] == "MRP: ₹120"


def test_missing_image_is_structured_failure(monkeypatch):
    def fail(path):
        raise ValueError("Image file does not exist")
    monkeypatch.setattr("src.service.preprocess_image", fail)
    result = process_inspection({"product_id": "P1"}, ["missing.png"], [])
    assert result["status"] == "FAILED"
    assert result["errors"][0]["stage"] == "image_processing"


def test_partial_image_failure_preserves_success(monkeypatch):
    def process(path):
        if path == "bad.png":
            raise ValueError("bad image")
        return {"processed": "processed", "metadata": {}}
    monkeypatch.setattr("src.service.preprocess_image", process)
    monkeypatch.setattr("src.service.run_ocr", lambda image: {"text": "", "confidence": None, "words": [], "lines": [], "engine": "mock", "error": "no text"})
    result = process_inspection({"product_id": "P1"}, ["good.png", "bad.png"], [])
    assert result["status"] == "COMPLETED"
    assert {item["status"] for item in result["images"]} == {"COMPLETED_WITH_WARNING", "FAILED"}


def test_service_accepts_uploaded_bytes_and_preserves_image_id(monkeypatch):
    monkeypatch.setattr("src.service.preprocess_image", lambda source: {"processed": "processed", "metadata": {"processing_steps": ["decoded"]}})
    monkeypatch.setattr("src.service.run_ocr", lambda image: {"text": "MRP: ₹120", "confidence": 90, "words": [], "lines": [], "engine": "mock", "error": None, "ocr_status": "SUCCESS"})
    result = process_inspection({"product_id": "P1"}, [{"image_id": "back_panel", "name": "back.webp", "bytes": b"webp-bytes"}], [])
    assert result["images"][0]["image_id"] == "back_panel"
    assert result["images"][0]["decoding_status"] == "SUCCESS"
    assert result["ocr"][0]["image_id"] == "back_panel"
