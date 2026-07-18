"""
tests/test_ocr_routing.py — verifies GPU-aware OCR routing and accurate
switching between PaddleOCR (PRINTED_TEXT / TABLE) and Qwen2.5-VL (HANDWRITTEN).

The Qwen (handwritten) engine needs a CUDA GPU microservice; to keep this test
CPU-only and deterministic we monkeypatch the Qwen wrapper so it returns a
fake transcription. The routing *decision* (which engine is selected, and the
self-check fallback) is what we assert.

Run under the project's Python 3.12 venv, with the backend package importable.
"""
import os
import sys
import site
import tempfile
from pathlib import Path

import numpy as np

# Env shims so paddleocr 2.8.1 imports under NumPy 2.x / this layout:
# 1) paddleocr 2.8.1 references np.sctypes (removed in NumPy 2.0)
if not hasattr(np, "sctypes"):
    np.sctypes = {
        "int": [np.int8, np.int16, np.int32, np.int64],
        "uint": [np.uint8, np.uint16, np.uint32, np.uint64],
        "float": [np.float16, np.float32, np.float64],
        "complex": [np.complex64, np.complex128],
        "others": [bool, object, bytes, str, np.void],
    }
# 2) paddleocr does `from tools.infer import ...`; its tools package lives in
#    site-packages/paddleocr/tools, so prepend that dir to sys.path.
for _sp in site.getsitepackages():
    if os.path.isdir(os.path.join(_sp, "paddleocr", "tools")):
        sys.path.insert(0, os.path.join(_sp, "paddleocr"))
        break

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
sys.path.append(str(ROOT))  # so `backend.classifier` resolves

from PIL import Image, ImageDraw, ImageFont  # noqa: E402


def _font(size=22):
    try:
        return ImageFont.truetype("arial.ttf", size)
    except Exception:
        return ImageFont.load_default()


def make_printed(path: Path):
    img = Image.new("RGB", (600, 400), "white")
    d = ImageDraw.Draw(img)
    d.text((20, 20), "Patient: John Doe", fill="black", font=_font())
    d.text((20, 70), "HbA1c: 6.8 %  (ref 4.0-5.6)", fill="black", font=_font())
    d.text((20, 120), "Glucose: 142 mg/dL", fill="black", font=_font())
    d.text((20, 170), "Cholesterol: 210 mg/dL", fill="black", font=_font())
    img.save(path)


def make_table(path: Path):
    img = Image.new("RGB", (600, 400), "white")
    d = ImageDraw.Draw(img)
    rows = ["Test | Result | Unit | Ref",
            "WBC | 6.2 | 10^9/L | 4-11",
            "RBC | 4.8 | 10^12/L | 4.2-5.4",
            "Hgb | 13.5 | g/dL | 13-17",
            "PLT | 250 | 10^9/L | 150-400"]
    y = 20
    for r in rows:
        d.text((20, y), r, fill="black", font=_font())
        y += 40
    for x in (20, 260, 420, 560):
        d.line([(x, 10), (x, 380)], fill="black", width=1)
    img.save(path)


def make_handwritten(path: Path):
    img = Image.new("RGB", (600, 400), "white")
    d = ImageDraw.Draw(img)
    rng = np.random.default_rng(0)
    for _ in range(40):
        x0, y0 = int(rng.integers(20, 580)), int(rng.integers(20, 380))
        x1, y1 = int(rng.integers(20, 580)), int(rng.integers(20, 380))
        d.line([(x0, y0), (x1, y1)], fill="black", width=int(rng.integers(1, 3)))
    d.text((30, 30), "note", fill="black", font=_font(34))
    img.save(path)


@pytest.fixture
def fake_qwen(monkeypatch):
    """Stub the Qwen wrapper factory so no CUDA/GPU microservice is needed."""
    import services.ocr_service as osvc

    class FakeQwen:
        def extract_text(self, filepath, filetype):
            return "HANDWRITTEN TRANSCRIPT: patient reports fatigue and cough."
        def extract_structured(self, filepath, filetype):
            return [{"test_name": "note", "value": "handwritten", "unit": "", "reference_range": ""}]

    def _fake_get_qwen_wrapper(**kwargs):
        return FakeQwen()

    monkeypatch.setattr(osvc, "_get_qwen_wrapper", _fake_get_qwen_wrapper)
    yield


def test_routing_printed_and_table_use_paddle(fake_qwen):
    from services.ocr_service import AutoOCRProvider
    tmp = Path(tempfile.gettempdir())
    p_img = tmp / "t_printed.png"; make_printed(p_img)
    t_img = tmp / "t_table.png"; make_table(t_img)

    ocr = AutoOCRProvider()
    tp = ocr.extract_text(str(p_img), "image")
    assert tp.strip(), "printed OCR returned empty"
    assert ocr.last_doc_type in ("PRINTED_TEXT", "TABLE")
    assert "PaddleOCR" in ocr.last_provider.__class__.__name__, ocr.last_provider.__class__.__name__

    ot = ocr.extract_text(str(t_img), "image")
    assert ot.strip(), "table OCR returned empty"
    assert "PaddleOCR" in ocr.last_provider.__class__.__name__, ocr.last_provider.__class__.__name__


def test_routing_handwritten_uses_qwen_when_confident(fake_qwen):
    from services.ocr_service import AutoOCRProvider

    tmp = Path(tempfile.gettempdir())
    h_img = tmp / "t_hand.png"; make_handwritten(h_img)

    ocr = AutoOCRProvider()
    class FakeCls:
        def predict_3class(self, img):
            from backend.classifier import ClassificationResult
            return ClassificationResult(doc_class="HANDWRITTEN", confidence=0.95)
    ocr._classifier = FakeCls()

    text = ocr.extract_text(str(h_img), "image")
    assert "HANDWRITTEN TRANSCRIPT" in text, text
    assert ocr.last_doc_type == "HANDWRITTEN"
    assert "Qwen" in type(ocr.last_provider).__name__, type(ocr.last_provider).__name__


def test_self_check_fallback_when_paddle_empty(monkeypatch, fake_qwen):
    from services.ocr_service import AutoOCRProvider

    def _empty_paddle(*a, **k):
        class Empty:
            def extract_text(self, fp, ft):
                return ""
            def extract_structured(self, fp, ft):
                return []
        return Empty()
    monkeypatch.setattr("services.ocr_service._get_paddle_wrapper", _empty_paddle)

    tmp = Path(tempfile.gettempdir())
    p_img = tmp / "t_fallback.png"; make_printed(p_img)
    ocr = AutoOCRProvider()
    text = ocr.extract_text(str(p_img), "image")
    assert "HANDWRITTEN TRANSCRIPT" in text, text
