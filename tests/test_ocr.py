from pathlib import Path

import numpy as np

from src.ocr import OCRConfigurationError, OCRInputError, OCRResult, OCREngine, run_ocr, run_ocr_on_images
from src.preprocessing import preprocess_image

SAMPLE = Path(__file__).parents[1] / "samples" / "package_images" / "demo_p001_complete.png"


def test_ocr_result_contract_imports():
    result = OCRResult("text", 90.0, [], [])
    assert set(("text", "confidence", "words", "lines", "engine")).issubset(result.as_dict())


def test_invalid_image_is_handled():
    result = run_ocr(np.array([], dtype=np.uint8))
    assert result.text == ""
    assert result.error and "empty" in result.error.lower()


def test_missing_tesseract_configuration_is_clear(monkeypatch):
    def unavailable():
        raise OCRConfigurationError("Tesseract OCR is not available. Install Tesseract and add it to PATH, or set TESSERACT_CMD to its executable.")
    monkeypatch.setattr("src.ocr.configure_tesseract", unavailable)
    result = run_ocr(np.zeros((20, 20), dtype=np.uint8))
    assert result.error and "Tesseract OCR is not available" in result.error


def test_empty_ocr_result_is_structured(monkeypatch):
    monkeypatch.setattr("src.ocr.configure_tesseract", lambda: None)
    monkeypatch.setattr("src.ocr.pytesseract.image_to_data", lambda *args, **kwargs: {"text": [], "conf": []})
    result = run_ocr(np.zeros((20, 20), dtype=np.uint8))
    assert result.text == ""
    assert result.confidence is None
    assert result.error == "OCR completed but detected no text."


def test_word_and_line_structure(monkeypatch):
    monkeypatch.setattr("src.ocr.configure_tesseract", lambda: None)
    data = {"text": ["MRP", "120"], "conf": [92, 88], "left": [1, 40], "top": [2, 2], "width": [30, 25], "height": [10, 10], "block_num": [1, 1], "par_num": [1, 1], "line_num": [1, 1]}
    monkeypatch.setattr("src.ocr.pytesseract.image_to_data", lambda *args, **kwargs: data)
    result = run_ocr(np.zeros((20, 80), dtype=np.uint8))
    assert result.text == "MRP 120"
    assert result.confidence == 90
    assert result.words[0]["x"] == 1
    assert all(isinstance(word[key], int) for word in result.words for key in ("x", "y", "width", "height"))
    assert result.lines[0]["text"] == "MRP 120"


def test_multiple_images_remain_separate(monkeypatch):
    monkeypatch.setattr("src.ocr.configure_tesseract", lambda: None)
    monkeypatch.setattr("src.ocr.pytesseract.image_to_data", lambda *args, **kwargs: {"text": [], "conf": []})
    results = run_ocr_on_images([("front", np.zeros((10, 10), dtype=np.uint8)), ("back", np.zeros((10, 10), dtype=np.uint8))])
    assert [item["image_id"] for item in results] == ["front", "back"]
