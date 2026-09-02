from pathlib import Path

import numpy as np
import pytest

from src.preprocessing import ImagePreprocessingError, convert_to_grayscale, preprocess_image, resize_image

SAMPLE = Path(__file__).parents[1] / "samples" / "package_images" / "demo_p001_complete.png"


def test_valid_image_loads_successfully():
    result = preprocess_image(SAMPLE)
    assert isinstance(result, dict)
    assert result["original"].size > 0


def test_invalid_path_is_handled():
    with pytest.raises(ImagePreprocessingError, match="does not exist"):
        preprocess_image(SAMPLE.parent / "missing.png")


def test_invalid_image_is_handled(tmp_path):
    invalid = tmp_path / "invalid.png"
    invalid.write_bytes(b"not an image")
    with pytest.raises(ImagePreprocessingError, match="empty|decoded"):
        preprocess_image(invalid)


def test_uploaded_bytes_are_decoded_without_a_filesystem_path():
    encoded = SAMPLE.read_bytes()
    result = preprocess_image(encoded)
    assert result["original"].size > 0
    assert result["processed"].size > 0


def test_grayscale_conversion_produces_one_channel_image():
    grayscale = convert_to_grayscale(np.zeros((20, 30, 3), dtype=np.uint8))
    assert grayscale.shape == (20, 30)


def test_processed_image_is_not_empty():
    result = preprocess_image(SAMPLE)
    assert result["processed"].size > 0
    assert result["processed"].ndim == 2


def test_original_metadata_and_aspect_ratio_are_preserved():
    result = preprocess_image(SAMPLE, max_width=100, max_height=100)
    metadata = result["metadata"]
    assert metadata["original_width"] >= result["original"].shape[1]
    original_ratio = metadata["original_width"] / metadata["original_height"]
    processed_ratio = metadata["processed_width"] / metadata["processed_height"]
    assert abs(original_ratio - processed_ratio) < 0.1


def test_resize_does_not_enlarge_small_images():
    resized = resize_image(np.zeros((20, 40, 3), dtype=np.uint8), 100, 100)
    assert resized.shape[:2] == (20, 40)
