"""Reusable OpenCV preprocessing for package-label images.

This module deliberately knows nothing about OCR, rules, persistence, or Streamlit.
The source image is never modified; the returned ``PreparedImage`` contains both
the original decoded color image and a separate OCR-ready image.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image

SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
MAX_IMAGE_WIDTH = 1800
MAX_IMAGE_HEIGHT = 1800


class ImagePreprocessingError(ValueError):
    """Application-level error for invalid or unusable image input."""


class PreparedImage(dict):
    """Dictionary result with attribute compatibility for earlier callers."""

    def __init__(self, original: np.ndarray, processed: np.ndarray, metadata: dict[str, Any]):
        super().__init__(original=original, processed=processed, metadata=metadata)

    @property
    def original(self) -> np.ndarray:
        return self["original"]

    @property
    def processed(self) -> np.ndarray:
        return self["processed"]

    @property
    def metadata(self) -> dict[str, Any]:
        return self["metadata"]


def validate_image_path(image_path: str | Path) -> Path:
    """Validate existence and supported extension before decoding."""
    path = Path(image_path)
    if not path.exists() or not path.is_file():
        raise ImagePreprocessingError(f"Image file does not exist: {path}")
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise ImagePreprocessingError(f"Unsupported image format '{path.suffix}'. Supported formats: {supported}")
    return path


def validate_image(image: np.ndarray | None) -> np.ndarray:
    """Validate a decoded OpenCV image and return it unchanged."""
    if image is None or not isinstance(image, np.ndarray) or image.size == 0:
        raise ImagePreprocessingError("The image is empty or could not be decoded.")
    if image.ndim not in (2, 3) or image.shape[0] <= 0 or image.shape[1] <= 0:
        raise ImagePreprocessingError("The image has invalid dimensions.")
    return image


def load_image(image_path: str | Path | bytes) -> np.ndarray:
    """Decode a path or byte payload as a color OpenCV image."""
    if isinstance(image_path, bytes):
        if not image_path:
            raise ImagePreprocessingError("The supplied image bytes are empty.")
        decoded = cv2.imdecode(np.frombuffer(image_path, dtype=np.uint8), cv2.IMREAD_COLOR)
    else:
        path = validate_image_path(image_path)
        decoded = cv2.imread(str(path), cv2.IMREAD_COLOR)
    return validate_image(decoded)


def resize_image(image: np.ndarray, max_width: int = MAX_IMAGE_WIDTH, max_height: int = MAX_IMAGE_HEIGHT) -> np.ndarray:
    """Downscale oversized images without changing aspect ratio or enlarging small ones."""
    validate_image(image)
    height, width = image.shape[:2]
    scale = min(max_width / width, max_height / height, 1.0)
    if scale == 1.0:
        return image.copy()
    return cv2.resize(image, (max(1, round(width * scale)), max(1, round(height * scale))), interpolation=cv2.INTER_AREA)


def convert_to_grayscale(image: np.ndarray) -> np.ndarray:
    """Convert a color image to one-channel grayscale."""
    validate_image(image)
    if image.ndim == 2:
        return image.copy()
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def enhance_contrast(image: np.ndarray, clip_limit: float = 2.0, tile_grid_size: tuple[int, int] = (8, 8)) -> np.ndarray:
    """Apply moderate CLAHE contrast enhancement."""
    validate_image(image)
    return cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid_size).apply(image)


def denoise_image(image: np.ndarray, kernel_size: int = 3) -> np.ndarray:
    """Apply light Gaussian denoising while retaining small character strokes."""
    validate_image(image)
    if kernel_size < 1 or kernel_size % 2 == 0:
        raise ImagePreprocessingError("Denoising kernel size must be a positive odd number.")
    return cv2.GaussianBlur(image, (kernel_size, kernel_size), 0)


def threshold_image(image: np.ndarray, method: str = "otsu") -> np.ndarray:
    """Convert grayscale input to OCR-friendly binary pixels."""
    validate_image(image)
    if image.ndim != 2:
        raise ImagePreprocessingError("Thresholding requires a grayscale image.")
    if method == "otsu":
        return cv2.threshold(image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    if method == "adaptive":
        return cv2.adaptiveThreshold(image, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 11)
    raise ImagePreprocessingError(f"Unknown threshold method: {method}")


def prepare_for_ocr(image: np.ndarray, threshold_method: str = "otsu") -> np.ndarray:
    """Run grayscale → CLAHE → denoise → threshold."""
    grayscale = convert_to_grayscale(image)
    enhanced = enhance_contrast(grayscale)
    denoised = denoise_image(enhanced)
    return threshold_image(denoised, threshold_method)


def preprocess_image(image_path: str | Path | bytes, max_width: int = MAX_IMAGE_WIDTH, max_height: int = MAX_IMAGE_HEIGHT) -> PreparedImage:
    """Load, validate, resize, and prepare an image without overwriting its source."""
    original_decoded = load_image(image_path)
    working_color = resize_image(original_decoded, max_width, max_height)
    processed = prepare_for_ocr(working_color)
    metadata = {
        "original_width": int(original_decoded.shape[1]),
        "original_height": int(original_decoded.shape[0]),
        "processed_width": int(processed.shape[1]),
        "processed_height": int(processed.shape[0]),
        "original_channels": int(1 if original_decoded.ndim == 2 else original_decoded.shape[2]),
        "processing_steps": ["validated", "resized_if_oversized", "grayscale", "clahe_contrast", "gaussian_denoise", "threshold_otsu"],
    }
    return PreparedImage(original=working_color, processed=processed, metadata=metadata)


def image_to_png_bytes(image: np.ndarray) -> bytes:
    """Encode an OpenCV image for later evidence display or persistence."""
    validate_image(image)
    ok, encoded = cv2.imencode(".png", image)
    if not ok:
        raise ImagePreprocessingError("Unable to encode image evidence.")
    return encoded.tobytes()


def pil_to_bytes(image: Image.Image, format: str = "PNG") -> bytes:
    """Compatibility helper for callers that already hold a Pillow image."""
    output = BytesIO()
    image.save(output, format=format)
    return output.getvalue()

