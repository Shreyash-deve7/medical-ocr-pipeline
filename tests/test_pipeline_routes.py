"""
tests/test_pipeline_routes.py — Session 8 /api/pipeline/run route tests (offline).

Drives ``POST /api/pipeline/run`` through ``TestClient`` with the OCR backend
faked (monkeypatching ``ocr_router_agent.AGENT_FACTORIES``) and LLM clients
unset, so nothing requires GPU / network / real models. Mirrors the setup of
``test_routes_integration.py`` (temp DB + uploads dir set BEFORE backend import).
"""
import os
import sys
import tempfile

import numpy as np
import cv2

_TMP = tempfile.mkdtemp(prefix="medvault_pipeline_")
os.environ["DB_PATH"] = os.path.join(_TMP, "medapp.db")
os.environ["UPLOAD_DIR"] = os.path.join(_TMP, "uploads")

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from fastapi.testclient import TestClient
from backend.main import app
import database as db_module
from agents.ocr_result import OCRResult


def _table_png_bytes(w=600, h=800, rows=18, cols=4):
    img = np.ones((h, w, 3), dtype=np.uint8) * 255
    for r in range(rows + 1):
        y = int((r / rows) * (h - 40)) + 20
        cv2.line(img, (40, y), (w - 40, y), (0, 0, 0), 2)
    for c in range(cols + 1):
        x = int((c / cols) * (w - 80)) + 40
        cv2.line(img, (x, 20), (x, h - 20), (0, 0, 0), 2)
    ok, buf = cv2.imencode(".png", img)
    return buf.tobytes()

KNOWN_OCR_TEXT = (
    "Alanine Aminotransferase 78 U/L\n"
    "Aspartate Aminotransferase 65 U/L\n"
    "Albumin 3.2 g/dL"
)


class _FakeOCRAgent:
    def run(self, image):
        return OCRResult(raw_output=KNOWN_OCR_TEXT, engine="FakeOCR",
                         confidence=0.9, processing_time_seconds=0.0)


@pytest.fixture
def client(monkeypatch):
    from agents import ocr_router_agent
    monkeypatch.setattr(
        ocr_router_agent, "AGENT_FACTORIES",
        {k: (lambda: _FakeOCRAgent()) for k in
         ("TABLE", "HANDWRITTEN", "PRINTED_TEXT", "printed", "handwritten")},
    )
    db_module.init_db()
    with TestClient(app) as c:
        yield c


def _png_bytes():
    return _table_png_bytes()


def test_pipeline_run_returns_valid_result(client):
    r = client.post("/api/pipeline/run",
                    files={"file": ("doc.png", _png_bytes(), "image/png")})
    assert r.status_code == 200
    body = r.json()
    for key in ("preprocessing", "classification", "lab_report", "diagnosis", "metadata"):
        assert key in body
    assert body["diagnosis"].get("summary_for_doctor")
    assert body["metadata"]["use_graph"] is True


def test_pipeline_run_with_summary_and_evaluate(client):
    r = client.post("/api/pipeline/run",
                    files={"file": ("doc.png", _png_bytes(), "image/png")},
                    data={"summary": "true", "evaluate": "true"})
    assert r.status_code == 200
    body = r.json()
    assert "summary" in body
    assert body["metadata"]["summary"] is True
    # evaluation is present (None if fixtures absent, dict otherwise)
    assert "evaluation" in body


def test_pipeline_run_use_graph_false(client):
    r = client.post("/api/pipeline/run",
                    files={"file": ("doc.png", _png_bytes(), "image/png")},
                    data={"use_graph": "false"})
    assert r.status_code == 200
    assert r.json()["metadata"]["use_graph"] is False


def test_pipeline_run_rejects_empty_file(client):
    r = client.post("/api/pipeline/run",
                    files={"file": ("doc.png", b"", "image/png")})
    assert r.status_code == 400


def test_pipeline_run_rejects_missing_file(client):
    r = client.post("/api/pipeline/run", data={})
    # FastAPI rejects a missing required UploadFile with 422.
    assert r.status_code in (400, 422)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
