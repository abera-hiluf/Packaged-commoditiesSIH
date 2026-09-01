"""OCR abstraction with an optional Tesseract implementation."""

from dataclasses import dataclass, asdict
from typing import Any

import cv2
import pytesseract


@dataclass
class OCRResult:
    text: str
    confidence: float | None
    words: list[dict[str, Any]]
    engine: str
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class OCREngine:
    """Replaceable OCR interface; confidence is OCR confidence only."""

    def extract(self, image) -> OCRResult:
        try:
            data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
            words = []
            confidences = []
            for i, raw in enumerate(data.get("text", [])):
                word = str(raw).strip()
                try:
                    conf = float(data["conf"][i])
                except (ValueError, TypeError, KeyError):
                    conf = -1
                if word:
                    words.append({"text": word, "confidence": conf, "left": data["left"][i], "top": data["top"][i], "width": data["width"][i], "height": data["height"][i]})
                    if conf >= 0:
                        confidences.append(conf)
            return OCRResult(" ".join(w["text"] for w in words), sum(confidences) / len(confidences) if confidences else None, words, "tesseract")
        except Exception as exc:
            return OCRResult("", None, [], "tesseract", str(exc))


def run_ocr(image) -> OCRResult:
    return OCREngine().extract(image)

