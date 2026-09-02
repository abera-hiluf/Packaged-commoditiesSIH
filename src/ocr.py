"""Replaceable Tesseract OCR abstraction.

OCR confidence describes recognition quality only. It is never a legal,
compliance, or extraction confidence score.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from typing import Any, Iterable

import numpy as np
import pytesseract


class OCRConfigurationError(RuntimeError):
    """Raised when Tesseract is not installed or configured."""


class OCRInputError(ValueError):
    """Raised when OCR receives an empty or invalid image."""


@dataclass
class OCRResult:
    text: str
    confidence: float | None
    words: list[dict[str, Any]]
    lines: list[dict[str, Any]]
    engine: str = "tesseract"
    config: str = "--oem 3 --psm 6"
    raw_data: dict[str, Any] | None = None
    error: str | None = None

    @property
    def status(self) -> str:
        if self.error and not self.text:
            return "NO_TEXT" if self.error == "OCR completed but detected no text." else "FAILED"
        return "SUCCESS"

    def as_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["ocr_status"] = self.status
        result["raw_text"] = self.text
        result["ocr_confidence"] = self.confidence
        return result


def configure_tesseract() -> None:
    """Use TESSERACT_CMD when supplied, otherwise check standard locations and PATH."""
    command = os.getenv("TESSERACT_CMD")
    if command:
        pytesseract.pytesseract.tesseract_cmd = command
    else:
        standard_candidates = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
            os.path.expandvars(r"%LOCALAPPDATA%\Tesseract-OCR\tesseract.exe"),
        ]
        for candidate in standard_candidates:
            if os.path.isfile(candidate):
                pytesseract.pytesseract.tesseract_cmd = candidate
                break
    try:
        pytesseract.get_tesseract_version()
    except Exception as exc:
        raise OCRConfigurationError("Tesseract OCR is not available. Install Tesseract and add it to PATH, or set TESSERACT_CMD to its executable.") from exc


def _validate_image(image: Any) -> np.ndarray:
    if not isinstance(image, np.ndarray) or image.size == 0:
        raise OCRInputError("OCR received an empty or invalid image.")
    if image.ndim not in (2, 3) or image.shape[0] <= 0 or image.shape[1] <= 0:
        raise OCRInputError("OCR received an image with invalid dimensions.")
    return image


def _number(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _confidence(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def _build_lines(data: dict[str, list[Any]], words: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group valid tokens by Tesseract block/paragraph/line identifiers."""
    groups: dict[tuple[int, int, int], list[dict[str, Any]]] = {}
    for word in words:
        index = word["index"]
        key = (_number(data.get("block_num", [0])[index]), _number(data.get("par_num", [0])[index]), _number(data.get("line_num", [0])[index]))
        groups.setdefault(key, []).append(word)
    lines = []
    for key, members in groups.items():
        members.sort(key=lambda item: item["x"])
        lines.append({"text": " ".join(item["text"] for item in members), "confidence": sum(item["confidence"] for item in members if item["confidence"] is not None) / max(1, sum(item["confidence"] is not None for item in members)), "x": min(item["x"] for item in members), "y": min(item["y"] for item in members), "width": max(item["x"] + item["width"] for item in members) - min(item["x"] for item in members), "height": max(item["y"] + item["height"] for item in members) - min(item["y"] for item in members), "block_num": key[0], "par_num": key[1], "line_num": key[2]})
    return sorted(lines, key=lambda line: (line["y"], line["x"]))


class OCREngine:
    """Tesseract-backed engine with a stable result contract."""

    def __init__(self, config: str = "--oem 3 --psm 6"):
        self.config = config

    def extract(self, image: np.ndarray) -> OCRResult:
        try:
            image = _validate_image(image)
            configure_tesseract()
            data = pytesseract.image_to_data(image, config=self.config, output_type=pytesseract.Output.DICT)
            words = []
            valid_confidences = []
            for index, raw_text in enumerate(data.get("text", [])):
                text = str(raw_text).strip()
                confidence = _confidence(data.get("conf", [None] * len(data.get("text", [])))[index])
                if not text:
                    continue
                word = {"text": text, "confidence": confidence, "x": _number(data.get("left", [0])[index]), "y": _number(data.get("top", [0])[index]), "width": _number(data.get("width", [0])[index]), "height": _number(data.get("height", [0])[index]), "index": index}
                words.append(word)
                if confidence is not None:
                    valid_confidences.append(confidence)
            lines = _build_lines(data, words)
            for word in words:
                word.pop("index", None)
            text = "\n".join(line["text"] for line in lines)
            return OCRResult(text=text, confidence=sum(valid_confidences) / len(valid_confidences) if valid_confidences else None, words=words, lines=lines, config=self.config, raw_data=data, error=None if text else "OCR completed but detected no text.")
        except (OCRConfigurationError, OCRInputError) as exc:
            return OCRResult("", None, [], [], config=self.config, error=str(exc))
        except Exception:
            return OCRResult("", None, [], [], config=self.config, error="Tesseract could not process this image. Check the image and Tesseract installation.")


def run_ocr(image: np.ndarray, config: str = "--oem 3 --psm 6") -> OCRResult:
    """Run OCR on one preprocessed image."""
    return OCREngine(config=config).extract(image)


def run_ocr_on_images(images: Iterable[tuple[str, np.ndarray] | dict[str, Any]]) -> list[dict[str, Any]]:
    """Process multiple images independently; text is intentionally not merged."""
    results = []
    for item in images:
        if isinstance(item, dict):
            image_id, image = item["image_id"], item["image"]
        else:
            image_id, image = item
        result = run_ocr(image)
        payload = result.as_dict()
        payload["image_id"] = image_id
        results.append(payload)
    return results
