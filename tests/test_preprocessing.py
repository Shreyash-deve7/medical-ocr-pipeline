"""
tests/test_preprocessing.py — Session 1 validation.

Verifies the preprocessing pipeline additions: deskew reduces skew, CLAHE
improves contrast, preprocess_image stays backward-compatible (ndarray),
and PreprocessingAgent returns a structured PreprocessingResult.
"""
import os
import sys
import numpy as np
import cv2
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from image_processing import (
    preprocess_image,
    enhance_contrast,
    quality_metrics,
    deskew,
)
from agents.preprocessing_agent import PreprocessingAgent, PreprocessingResult


def _make_document_image(width=600, height=800):
    """Synthetic medical-document-like image: white page with black text lines."""
    img = np.ones((height, width, 3), dtype=np.uint8) * 255
    # Horizontal text lines
    for y in range(60, height - 40, 40):
        cv2.line(img, (40, y), (width - 40, y), (0, 0, 0), 3)
    # A couple of vertical column separators (helps skew detection)
    cv2.line(img, (width // 2, 40), (width // 2, height - 40), (0, 0, 0), 2)
    return img


def _rotate(img, angle_deg):
    (h, w) = img.shape[:2]
    center = (w // 2, h // 2)
    rot = cv2.getRotationMatrix2D(center, angle_deg, 1.0)
    cos, sin = np.abs(rot[0, 0]), np.abs(rot[0, 1])
    new_w = int((h * sin) + (w * cos))
    new_h = int((h * cos) + (w * sin))
    rot[0, 2] += (new_w / 2) - center[0]
    rot[1, 2] += (new_h / 2) - center[1]
    return cv2.warpAffine(img, rot, (new_w, new_h),
                          flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)


def test_preprocess_image_returns_ndarray():
    img = _make_document_image()
    out = preprocess_image(img, do_deskew=False, do_denoise=False)
    assert isinstance(out, np.ndarray)
    assert out.ndim == 3 and out.shape[2] == 3


def test_deskew_reduces_skew():
    img = _make_document_image()
    skewed = _rotate(img, 7.0)
    before = abs(quality_metrics(skewed)["skew_angle_degrees"])
    corrected = deskew(skewed)
    after = abs(quality_metrics(corrected)["skew_angle_degrees"])
    # Skew should be substantially reduced (allow small residual)
    assert after < before * 0.6, f"skew not reduced: {before} -> {after}"


def _mean_local_contrast(img, tile=32):
    """Mean std-dev over non-overlapping tiles — captures local contrast (CLAHE's effect)."""
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    h, w = g.shape[:2]
    stds = []
    for y in range(0, h - tile + 1, tile):
        for x in range(0, w - tile + 1, tile):
            stds.append(float(g[y:y + tile, x:x + tile].std()))
    return float(np.mean(stds)) if stds else 0.0


def test_clahe_improves_contrast():
    # Low-contrast faded document: a gentle gradient with a faint ripple (little local contrast).
    h, w = 400, 400
    grad = np.tile(np.linspace(150, 200, w, dtype=np.float32), (h, 1))
    ripple = 8.0 * np.sin(np.linspace(0, 8 * np.pi, w)).astype(np.float32)
    grad = grad + ripple[None, :]
    img = np.dstack([grad, grad, grad]).astype(np.uint8)
    before = _mean_local_contrast(img)
    after = _mean_local_contrast(enhance_contrast(img))
    # CLAHE should boost local contrast by >=10%
    assert after >= before * 1.10, f"local contrast gain <10%: {before:.2f} -> {after:.2f}"


def test_preprocessing_result_structure():
    img = _make_document_image()
    result = PreprocessingAgent().run(img)
    assert isinstance(result, PreprocessingResult)
    assert isinstance(result.preprocessed_image, np.ndarray)
    assert len(result.transformations_applied) > 0
    # Symmetric synthetic image has ~0 skew, so deskew is a no-op; CLAHE always applies.
    assert "clahe" in result.transformations_applied
    assert result.quality_metrics_before and result.quality_metrics_after
    assert abs(result.quality_metrics_after["skew_angle_degrees"]) < 10


def test_preprocessing_applies_deskew_on_skewed():
    img = _make_document_image()
    skewed = _rotate(img, 5.0)
    result = PreprocessingAgent().run(skewed)
    assert "deskew" in result.transformations_applied


def test_preprocessing_reduces_skew_on_skewed_input():
    img = _make_document_image()
    skewed = _rotate(img, -6.0)
    result = PreprocessingAgent().run(skewed)
    before = abs(result.quality_metrics_before["skew_angle_degrees"])
    after = abs(result.quality_metrics_after["skew_angle_degrees"])
    assert after < before * 0.6


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
