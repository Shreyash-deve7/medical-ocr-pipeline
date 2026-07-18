"""
tests/test_ocr_router.py — Session 4 module tests for the OCR router.

Validates:
    - run_ocr() dispatches to the correct engine by doc_class
    - Unknown doc_class raises ValueError
    - Result dict contains all required fields
    - Each engine returns the expected shape of output
"""
import os
import sys
import numpy as np
import cv2
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from ocr.router import run_ocr


# ── Synthetic image builders ─────────────────────────────────────

def _make_table_image(w=600, h=800, rows=18, cols=4):
    img = np.ones((h, w, 3), dtype=np.uint8) * 255
    for r in range(rows + 1):
        y = int((r / rows) * (h - 40)) + 20
        cv2.line(img, (40, y), (w - 40, y), (0, 0, 0), 2)
    for c in range(cols + 1):
        x = int((c / cols) * (w - 80)) + 40
        cv2.line(img, (x, 20), (x, h - 20), (0, 0, 0), 2)
    return img


def _make_printed_image(w=600, h=800, spacing=40):
    img = np.ones((h, w, 3), dtype=np.uint8) * 255
    for y in range(60, h - 40, spacing):
        cv2.line(img, (40, y), (w - 40, y), (0, 0, 0), 3)
    return img


def _make_handwritten_image(w=600, h=800, seed=0):
    rng = np.random.default_rng(seed)
    img = np.ones((h, w, 3), dtype=np.uint8) * 255
    n_lines = 12
    for line_idx in range(n_lines):
        y_base = 60 + line_idx * 55
        x_start = 50 + int(rng.integers(0, 30))
        x_end = w - 50 - int(rng.integers(0, 30))
        pts = []
        for x in range(x_start, x_end, 5):
            y = int(y_base + 8 * np.sin(x * 0.05 + line_idx))
            pts.append([x, y])
        pts = np.array(pts, dtype=np.int32)
        cv2.polylines(img, [pts], False, (0, 0, 0), 2, cv2.LINE_AA)
        for x in range(x_start + 10, x_end - 10, 18):
            y = int(y_base + 8 * np.sin(x * 0.05 + line_idx))
            r = int(rng.integers(2, 12))
            cv2.circle(img, (x, y - 3), r, (0, 0, 0), -1)
    return img


# ── Field contract ──────────────────────────────────────────────

REQUIRED_FIELDS = {"doc_class", "raw_output", "ocr_engine_used", "processing_time_seconds"}


def _check_result_fields(result):
    assert isinstance(result, dict), "run_ocr must return a dict"
    assert REQUIRED_FIELDS.issubset(result.keys()), f"Missing fields: {REQUIRED_FIELDS - result.keys()}"
    assert result["doc_class"] in ("TABLE", "HANDWRITTEN", "PRINTED_TEXT")
    assert isinstance(result["processing_time_seconds"], float)
    assert result["processing_time_seconds"] >= 0.0


# ── Dispatch tests ──────────────────────────────────────────────

def test_run_ocr_table():
    img = _make_table_image()
    result = run_ocr(img, "TABLE")
    _check_result_fields(result)
    assert result["doc_class"] == "TABLE"
    assert isinstance(result["raw_output"], (str, list))


def test_run_ocr_printed_text():
    img = _make_printed_image()
    result = run_ocr(img, "PRINTED_TEXT")
    _check_result_fields(result)
    assert result["doc_class"] == "PRINTED_TEXT"


def test_run_ocr_handwritten():
    img = _make_handwritten_image()
    result = run_ocr(img, "HANDWRITTEN")
    _check_result_fields(result)
    assert result["doc_class"] == "HANDWRITTEN"


def test_run_ocr_unknown_class_raises():
    img = _make_printed_image()
    with pytest.raises(ValueError, match="Unknown doc_class"):
        run_ocr(img, "UNKNOWN_CLASS")


def test_run_ocr_timing_is_positive():
    img = _make_printed_image()
    result = run_ocr(img, "PRINTED_TEXT")
    assert result["processing_time_seconds"] >= 0.0


def test_run_ocr_engine_field_is_populated():
    img = _make_printed_image()
    result = run_ocr(img, "PRINTED_TEXT")
    assert result["ocr_engine_used"] != "unknown"
    assert isinstance(result["ocr_engine_used"], str)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))