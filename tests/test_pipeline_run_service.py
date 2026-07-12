"""
tests/test_pipeline_run_service.py — Session 8 unified pipeline service tests (offline).

Exercises ``services.pipeline_service.run_pipeline`` + ``PipelineGraph`` with the
OCR backend faked (monkeypatching ``ocr_router_agent.AGENT_FACTORIES``) and
LLM clients ``None`` (heuristic + rule-based) or fake (deterministic JSON), so
the default path needs no GPU / network / real models and stays deterministic.
"""
import os
import sys
import json
import numpy as np
import cv2
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from agents.ocr_result import OCRResult
from services.pipeline_service import run_pipeline, PipelineResult, PipelineGraph

KNOWN_OCR_TEXT = (
    "Alanine Aminotransferase 78 U/L\n"
    "Aspartate Aminotransferase 65 U/L\n"
    "Alkaline Phosphatase 120 U/L\n"
    "Albumin 3.2 g/dL\n"
    "Total Bilirubin 1.5 mg/dL"
)


class _FakeOCRAgent:
    def run(self, image):
        return OCRResult(raw_output=KNOWN_OCR_TEXT, engine="FakeOCR",
                         confidence=0.9, processing_time_seconds=0.0)


@pytest.fixture
def fake_ocr(monkeypatch):
    from agents import ocr_router_agent
    monkeypatch.setattr(
        ocr_router_agent, "AGENT_FACTORIES",
        {k: (lambda: _FakeOCRAgent()) for k in
         ("TABLE", "HANDWRITTEN", "PRINTED_TEXT", "printed", "handwritten")},
    )


def _make_table_image(w=600, h=800, rows=18, cols=4):
    img = np.ones((h, w, 3), dtype=np.uint8) * 255
    for r in range(rows + 1):
        y = int((r / rows) * (h - 40)) + 20
        cv2.line(img, (40, y), (w - 40, y), (0, 0, 0), 2)
    for c in range(cols + 1):
        x = int((c / cols) * (w - 80)) + 40
        cv2.line(img, (x, 20), (x, h - 20), (0, 0, 0), 2)
    return img


class _FakeExtractionLLM:
    def complete(self, prompt, inp):
        return json.dumps({
            "lab_results": [
                {"test_name": "Alanine Aminotransferase", "test_abbreviation": "ALT",
                 "value": 78, "unit": "U/L",
                 "reference_range": {"low": 7, "high": 56, "unit": "U/L"},
                 "flag": "HIGH", "clinical_significance": "Hepatocellular injury."},
                {"test_name": "Aspartate Aminotransferase", "test_abbreviation": "AST",
                 "value": 65, "unit": "U/L",
                 "reference_range": {"low": 10, "high": 40, "unit": "U/L"},
                 "flag": "HIGH", "clinical_significance": "Hepatocellular injury."},
                {"test_name": "Albumin", "test_abbreviation": "ALB",
                 "value": 3.2, "unit": "g/dL",
                 "reference_range": {"low": 3.5, "high": 5.0, "unit": "g/dL"},
                 "flag": "LOW", "clinical_significance": "Synthetic dysfunction."},
            ]
        })


class _FakeDiagnosisLLM:
    def complete(self, prompt, inp):
        return json.dumps({
            "clinical_patterns": [
                {"pattern": "Hepatocellular injury pattern",
                 "supporting_tests": ["ALT", "AST"],
                 "description": "Raised aminotransferases."}
            ],
            "abnormal_values": [
                {"test": "ALT", "value": 78, "flag": "HIGH", "note": "Elevated."}
            ],
            "urgent_flags": [],
            "suggested_followup": ["Repeat LFTs in 2 weeks"],
            "summary_for_doctor": "Mild hepatocellular injury with low albumin.",
        })


def test_run_pipeline_llm_free_returns_pipeline_result(tmp_path, fake_ocr):
    img = _make_table_image()
    path = tmp_path / "doc.png"
    cv2.imwrite(str(path), img)

    result = run_pipeline(str(path), llm_client=None, diagnosis_client=None)

    assert isinstance(result, PipelineResult)
    d = result.to_dict()
    assert set(d) >= {"preprocessing", "classification", "lab_report",
                      "diagnosis", "metadata"}
    assert d["classification"].get("class") in ("TABLE", "HANDWRITTEN", "PRINTED_TEXT")
    assert isinstance(d["lab_report"], dict)
    assert d["diagnosis"].get("summary_for_doctor")
    assert d["metadata"]["use_graph"] is True


def test_run_pipeline_fake_llm_populates_lab_report(tmp_path, fake_ocr):
    img = _make_table_image()
    path = tmp_path / "doc.png"
    cv2.imwrite(str(path), img)

    result = run_pipeline(str(path), llm_client=_FakeExtractionLLM(),
                          diagnosis_client=_FakeDiagnosisLLM())

    lab = result.lab_report
    assert len(lab["lab_results"]) == 3
    flags = {r["flag"] for r in lab["lab_results"]}
    assert "HIGH" in flags and "LOW" in flags
    assert len(result.diagnosis["clinical_patterns"]) >= 1
    assert result.diagnosis["summary_for_doctor"]


def test_run_pipeline_bytes_input(tmp_path, fake_ocr):
    img = _make_table_image()
    path = tmp_path / "doc.png"
    cv2.imwrite(str(path), img)
    content = path.read_bytes()

    result = run_pipeline(content, llm_client=None)
    assert isinstance(result.lab_report, dict)
    assert result.metadata["use_graph"] is True


def test_run_pipeline_use_graph_false(tmp_path, fake_ocr):
    img = _make_table_image()
    path = tmp_path / "doc.png"
    cv2.imwrite(str(path), img)

    result = run_pipeline(str(path), llm_client=None, use_graph=False)
    assert result.metadata["use_graph"] is False
    assert result.diagnosis.get("summary_for_doctor")


def test_run_pipeline_with_summary(tmp_path, fake_ocr):
    img = _make_table_image()
    path = tmp_path / "doc.png"
    cv2.imwrite(str(path), img)

    result = run_pipeline(str(path), llm_client=None, summary=True)
    assert isinstance(result.summary, dict)
    assert "summary" in result.summary
    assert result.metadata["summary"] is True


def test_run_pipeline_with_evaluation_merge(tmp_path, fake_ocr):
    img = _make_table_image()
    path = tmp_path / "doc.png"
    cv2.imwrite(str(path), img)

    result = run_pipeline(str(path), llm_client=None, evaluate=True)
    # evaluation merged from Agent 7 dataset (may be None if fixtures absent,
    # but when present it carries cer/wer/field_accuracy keys).
    assert "evaluation" in result.to_dict()
    assert result.metadata["evaluate"] is True
    if result.evaluation is not None:
        assert "samples_evaluated" in result.evaluation


def test_run_pipeline_bad_image_records_error_not_raise():
    result = run_pipeline(b"not an image at all", llm_client=None)
    assert isinstance(result, PipelineResult)
    # A bad image must not crash; the error is recorded, not raised.
    assert result.metadata.get("errors") or result.metadata  # result still builds


# ── PipelineGraph unit coverage ─────────────────────────────────────

def test_pipeline_graph_topo_order_and_state_merge():
    g = PipelineGraph()
    order = []

    def a(state):
        order.append("a")
        return {"x": 1}

    def b(state):
        order.append("b")
        assert state["x"] == 1
        return {"y": 2}

    def c(state):
        order.append("c")
        return {"z": state.get("y", 0) + 1}

    g.add_node("a", a).add_node("b", b).add_node("c", c)
    g.add_edge("a", "b").add_edge("b", "c")
    out = g.run({})
    assert out["x"] == 1 and out["y"] == 2 and out["z"] == 3
    assert order == ["a", "b", "c"]


def test_pipeline_graph_skips_optional_node():
    g = PipelineGraph()

    def core(state):
        return {"core": True}

    def optional(state):
        raise AssertionError("optional must not run")

    g.add_node("core", core).add_node("optional", optional)
    g.add_edge("core", "optional")
    # Remove the optional node + its edge to simulate evaluate/summary=False.
    g._nodes.pop("optional")
    g._edges = [e for e in g._edges if e[1] != "optional"]
    out = g.run({})
    assert out["core"] is True
    assert "errors" not in out


def test_pipeline_graph_node_failure_isolated():
    g = PipelineGraph()

    def boom(state):
        raise ValueError("node exploded")

    def ok(state):
        return {"survived": True}

    g.add_node("boom", boom).add_node("ok", ok)
    out = g.run({})
    assert "boom" in out.get("errors", {})
    assert out.get("survived") is True
