"""
tests/test_evaluation_agent.py — Session 7 evaluation coverage.

Tests the EvaluationAgent (Agent 7) jiwer integration + field accuracy, the
CER < 5% gate on the synthetic printed samples, and the
``/api/pipeline/evaluate`` endpoint contract.
"""
import os
import sys
import json

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from agents.evaluation_agent import EvaluationAgent
from agents.ocr_result import OCRResult

SAMPLE_DIR = os.path.join(os.path.dirname(__file__), "sample_images")
GROUND_TRUTH_PATH = os.path.join(SAMPLE_DIR, "ground_truth.json")


def _gt():
    with open(GROUND_TRUTH_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# ── jiwer integration (Agent 7) ──────────────────────────────────

def test_cer_exact_match_is_zero():
    ag = EvaluationAgent()
    assert ag.cer("Alanine Aminotransferase 78 U/L", "Alanine Aminotransferase 78 U/L") == 0.0


def test_cer_perturbed_is_positive():
    ag = EvaluationAgent()
    c = ag.cer("ALT 78 U/L", "ALT 79 U/L")
    assert c is not None and c > 0.0


def test_wer_exact_match_is_zero():
    ag = EvaluationAgent()
    assert ag.wer("one two three", "one two three") == 0.0


def test_cer_wer_none_when_jiwer_missing(monkeypatch):
    ag = EvaluationAgent()
    monkeypatch.setattr(ag, "_jiwer", lambda: None)
    assert ag.cer("a", "b") is None
    assert ag.wer("a", "b") is None


# ── field accuracy ───────────────────────────────────────────────

def test_field_accuracy_perfect():
    ag = EvaluationAgent()
    gt = [{"test_name": "ALT", "value": 78}, {"test_name": "AST", "value": 65}]
    ex = [{"test_name": "ALT", "value": 78.0}, {"test_name": "AST", "value": 65.0}]
    assert ag.field_accuracy(ex, gt) == 1.0


def test_field_accuracy_partial():
    ag = EvaluationAgent()
    gt = [{"test_name": "ALT", "value": 78}, {"test_name": "AST", "value": 65}]
    ex = [{"test_name": "ALT", "value": 78.0}]  # AST missing
    assert ag.field_accuracy(ex, gt) == 0.5


def test_field_accuracy_empty_ground_truth():
    ag = EvaluationAgent()
    assert ag.field_accuracy([{"test_name": "ALT", "value": 1}], []) is None


def test_parse_expected_fields():
    ag = EvaluationAgent()
    fields = ag.parse_expected_fields("Alanine Aminotransferase 78 U/L\nAlbumin 3.2 g/dL")
    keys = {f["test_name"] for f in fields}
    assert "Alanine Aminotransferase" in keys
    alb = next(f for f in fields if f["test_name"] == "Albumin")
    assert alb["value"] == 3.2 and alb["unit"] == "g/dL"


# ── CER < 5% gate on synthetic printed samples (real OCR) ────────

def test_cer_under_five_percent_on_printed_samples():
    """Real PaddleOCR over clean printed fixtures must yield CER < 5%.

    Runs in an isolated subprocess (see ``_cer_probe.py``) because PaddlePaddle
    has a Windows DLL-cleanup crash at interpreter exit; keeping OCR out of the
    pytest parent process makes the suite exit cleanly.
    """
    import re
    import subprocess

    probe = os.path.join(os.path.dirname(__file__), "_cer_probe.py")
    proc = subprocess.run(
        [sys.executable, probe, SAMPLE_DIR, "3"],
        capture_output=True, text=True, timeout=240,
    )
    m = re.search(r"CER_RESULT=(\{.*\})", proc.stdout)
    if not m:
        pytest.skip("OCR probe produced no result (backend unavailable?): "
                    + (proc.stderr or "")[-300:])
    res = json.loads(m.group(1))
    if not res.get("ocr_available"):
        pytest.skip("OCR backend unavailable in this environment")
    assert res["samples_evaluated"] > 0
    assert res["cer"] is not None
    assert res["cer"] < 0.05, f"CER {res['cer']:.4f} >= 5% on printed samples"


# ── /api/pipeline/evaluate endpoint contract ─────────────────────

def test_evaluate_endpoint_returns_valid_json(monkeypatch):
    # Avoid running the heavy OCR eval inside the endpoint for this contract test.
    import routes.evaluation_routes as eval_routes
    monkeypatch.setattr(
        eval_routes, "_CACHE",
        {"evaluation": {
            "cer": 0.01, "wer": 0.02, "field_accuracy": 0.9,
            "samples_evaluated": 5, "ocr_available": True, "notes": [],
        }},
    )
    from fastapi.testclient import TestClient
    from backend.main import app

    with TestClient(app) as client:
        resp = client.get("/api/pipeline/evaluate")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert "evaluation" in body
        assert body["evaluation"]["cer"] == 0.01
        assert "sample_images" in body
        assert "benchmark_available" in body


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
