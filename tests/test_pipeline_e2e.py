"""
tests/test_pipeline_e2e.py — Session 7 end-to-end pipeline test.

Chains the agents from an image path through to a validated ``LabReport`` JSON:

    image -> PreprocessingAgent -> ClassificationAgent -> OCRRouter
          -> ExtractionAgent -> ValidationAgent -> DiagnosisAgent

The OCR backend is faked (monkeypatching ``ocr_router_agent.AGENT_FACTORIES``)
so the default test path needs no GPU / network / real OCR models and stays
deterministic. Two variants are exercised:

  * LLM-free fallback chain (``llm_client=None`` everywhere) — relies on the
    heuristic extraction + rule-based diagnosis already built in Sessions 4/5.
  * Fake-LLM chain — a deterministic fake client returns valid JSON so the
    LLM code-path (prompt -> parse -> validate) is also covered end to end.

Mirrors the synthetic-fixture convention used in Sessions 2/3.
"""
import os
import sys
import json
import numpy as np
import cv2
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from agents.ocr_result import OCRResult
from agents.preprocessing_agent import PreprocessingAgent
from agents.classification_agent import ClassificationAgent
from agents.extraction_agent import ExtractionAgent
from agents.validation_agent import ValidationAgent
from agents.diagnosis_agent import DiagnosisAgent

KNOWN_OCR_TEXT = (
    "Alanine Aminotransferase 78 U/L\n"
    "Aspartate Aminotransferase 65 U/L\n"
    "Alkaline Phosphatase 120 U/L\n"
    "Albumin 3.2 g/dL\n"
    "Total Bilirubin 1.5 mg/dL"
)


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


# ── Fake LLM clients ─────────────────────────────────────────────

class _FakeExtractionLLM:
    def complete(self, prompt: str, inp: str) -> str:
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
    def complete(self, prompt: str, inp: str) -> str:
        return json.dumps({
            "clinical_patterns": [
                {"pattern": "Hepatocellular injury pattern",
                 "supporting_tests": ["ALT", "AST"],
                 "description": "Raised aminotransferases."}
            ],
            "abnormal_values": [
                {"test": "ALT", "value": 78, "flag": "HIGH",
                 "note": "Elevated transaminase."}
            ],
            "urgent_flags": [],
            "suggested_followup": ["Repeat LFTs in 2 weeks"],
            "summary_for_doctor": "Mild hepatocellular injury with low albumin.",
        })


# ── OCR fake (monkeypatched into the router) ─────────────────────

class _FakeOCRAgent:
    def run(self, image):
        return OCRResult(raw_output=KNOWN_OCR_TEXT, engine="FakeOCR",
                         confidence=0.9, processing_time_seconds=0.0)


@pytest.fixture
def fake_ocr(monkeypatch):
    """Route every doc_class through a deterministic fake OCR agent."""
    from agents import ocr_router_agent
    monkeypatch.setattr(
        ocr_router_agent, "AGENT_FACTORIES",
        {k: (lambda: _FakeOCRAgent()) for k in
         ("TABLE", "HANDWRITTEN", "PRINTED_TEXT", "printed", "handwritten")},
    )


def _run_chain(image_path, llm_client=None, diagnosis_client=None):
    """Full image-path -> LabReport -> DiagnosisResult chain (OCR faked)."""
    img = cv2.imread(image_path)
    assert img is not None
    pre = PreprocessingAgent().run(img)
    cls = ClassificationAgent(llm_client=llm_client).run(pre.preprocessed_image)

    from agents.ocr_router_agent import run_ocr
    ocr = run_ocr(pre.preprocessed_image, cls.doc_class)

    ext_agent = ExtractionAgent(llm_client=llm_client)
    ext = ext_agent.run(ocr)
    lab = ValidationAgent().run(ext, ocr, ext_agent)
    dx = DiagnosisAgent(llm_client=diagnosis_client).run(lab)
    return pre, cls, ocr, ext, lab, dx


def test_full_pipeline_llm_free(tmp_path, fake_ocr):
    """Image path -> LabReport with no LLM (heuristic + rule-based fallback)."""
    img_path = tmp_path / "doc.png"
    cv2.imwrite(str(img_path), _make_table_image())

    pre, cls, ocr, ext, lab, dx = _run_chain(str(img_path), llm_client=None,
                                             diagnosis_client=None)

    assert cls.doc_class in ("TABLE", "HANDWRITTEN", "PRINTED_TEXT")
    assert isinstance(ocr, OCRResult)
    assert ocr.engine == "FakeOCR"
    # LabReport validates regardless of how many fields heuristics recovered.
    assert lab.__class__.__name__ == "LabReport"
    assert isinstance(lab.lab_results, list)
    # Diagnosis produced a structured, schema-valid result (rule-based).
    assert dx.__class__.__name__ == "DiagnosisResult"
    assert dx.summary_for_doctor  # required field populated


def test_full_pipeline_fake_llm(tmp_path, fake_ocr):
    """Image path -> LabReport with deterministic fake LLM for extract+diagnose."""
    img_path = tmp_path / "doc.png"
    cv2.imwrite(str(img_path), _make_table_image())

    pre, cls, ocr, ext, lab, dx = _run_chain(
        str(img_path), llm_client=_FakeExtractionLLM(),
        diagnosis_client=_FakeDiagnosisLLM())

    # Extraction produced populated, validated results.
    assert len(lab.lab_results) == 3
    names = {r.test_name for r in lab.lab_results}
    assert "Alanine Aminotransferase" in names
    # At least one abnormal value flagged.
    flags = {r.flag for r in lab.lab_results}
    assert "HIGH" in flags and "LOW" in flags
    # Diagnosis consumed the validated report.
    assert len(dx.clinical_patterns) >= 1
    assert dx.summary_for_doctor


def test_pipeline_output_is_valid_json(tmp_path, fake_ocr):
    """The LabReport serialises to valid JSON matching the IBM §6.4 contract."""
    img_path = tmp_path / "doc.png"
    cv2.imwrite(str(img_path), _make_table_image())
    _, _, _, _, lab, dx = _run_chain(str(img_path), llm_client=_FakeExtractionLLM(),
                                     diagnosis_client=_FakeDiagnosisLLM())
    payload = json.loads(lab.model_dump_json())
    assert "lab_results" in payload
    assert all("flag" in r and "reference_range" in r for r in payload["lab_results"])
    diag = json.loads(dx.model_dump_json())
    assert "clinical_patterns" in diag and "summary_for_doctor" in diag


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
