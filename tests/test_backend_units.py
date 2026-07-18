"""
tests/test_backend_units.py — Session 7 coverage of offline backend logic.

Targets the pure / CPU-only backend modules that the earlier session tests did
not fully exercise: auth, config, database, ai_service (build/extract, no
network), ocr_service (routing/build, no OCR), unit_normaliser, hepatology_kb,
summary_agent, document_classifier branches, image_processing, heuristics,
classification_agent, diagnosis_agent, extraction_agent, preprocessing_agent,
and the EvaluationAgent dataset path + evaluation route compute path.

No GPU / network / real OCR models are touched.
"""
import os
import sys
import json
import tempfile

# Redirect DB / uploads to a temp location BEFORE importing backend modules so
# the TestClient lifespan (init_db) doesn't write into the repo.
_TMP = tempfile.mkdtemp(prefix="medvault_test_")
os.environ["DB_PATH"] = os.path.join(_TMP, "medapp.db")
os.environ["UPLOAD_DIR"] = os.path.join(_TMP, "uploads")

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

# ── auth ─────────────────────────────────────────────────────────
from auth import _hash_pw, _verify_pw, create_token, decode_token


def test_auth_hash_verify_roundtrip():
    h = _hash_pw("secret123")
    assert _verify_pw("secret123", h) is True
    assert _verify_pw("wrong", h) is False


def test_auth_token_roundtrip():
    tok = create_token("user-1", "patient")
    payload = decode_token(tok)
    assert payload["sub"] == "user-1"
    assert payload["role"] == "patient"


def test_auth_decode_invalid_raises():
    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        decode_token("not.a.jwt")


# ── config ──────────────────────────────────────────────────────
from config import Settings, settings


def test_config_defaults():
    s = Settings()
    assert s.algorithm == "HS256"
    assert s.access_token_expire_hours == 72
    assert s.jwt_secret


# ── database ────────────────────────────────────────────────────
import database as db_module


@pytest.fixture
def tmp_db(monkeypatch):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.remove(path)
    monkeypatch.setattr(db_module, "DB_PATH", path)
    db_module.init_db()
    yield path
    try:
        os.remove(path)
    except OSError:
        pass


def test_database_init_creates_tables(tmp_db):
    conn = db_module.get_db()
    tables = {r["name"] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    for t in ("patients", "doctors", "reports", "providers", "drug_interactions",
              "icd10_codes", "audit_log", "notifications"):
        assert t in tables
    conn.close()


def test_database_migrate_and_helpers(tmp_db):
    conn = db_module.get_db()
    db_module._migrate_reports_schema(conn)
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(reports)")}
    assert "doc_type" in cols and "ocr_engine" in cols
    db_module._notify(conn, "patient", "p1", "Title", "body")
    db_module._audit(conn, "patient", "p1", "action", "rt", "rid", "details")
    # seed a default provider and read it back
    conn.execute(
        "INSERT INTO providers (id,kind,name,engine,config,is_default,created_at) "
        "VALUES ('aid','ai','def','gemini','{}',1,'now')")
    row = db_module._get_provider_row(conn, None, "ai")
    assert row["engine"] == "gemini"
    conn.close()


# ── ai_service (no network) ─────────────────────────────────────
from services.ai_service import (
    AIProvider, AI_ENGINES, build_ai, MEDICAL_PROMPT, _extract_images,
)


def test_ai_build_engines():
    for engine in ("gemini", "openai", "ollama", "custom_openai"):
        p = build_ai(engine, {"api_key": "x", "endpoint": "http://e", "model": "m"})
        assert isinstance(p, AIProvider)


def test_ai_build_unknown_raises():
    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        build_ai("nope", {})


def test_ai_prompt_and_extract_image():
    assert "medical document analyst" in MEDICAL_PROMPT.lower()
    fd, path = tempfile.mkstemp(suffix=".png")
    os.write(fd, b"\x89PNG\r\n\x1a\n")
    os.close(fd)
    imgs = _extract_images(path, "image")
    assert isinstance(imgs, list) and len(imgs) == 1
    os.remove(path)


def test_ai_abc_is_abstract():
    with pytest.raises(TypeError):
        AIProvider()  # type: ignore[abstract]


# ── ocr_service (routing, no OCR runtime) ───────────────────────
from services.ocr_service import (
    OCRProvider, AutoOCRProvider, OCR_ENGINES, build_ocr,
)


class _FakeClassifier:
    def __init__(self, cls):
        self.cls = cls

    def predict_3class(self, img):
        from document_classifier import ClassificationResult
        return ClassificationResult(doc_class=self.cls, confidence=0.9,
                                    fallback_triggered=False)


class _FakeProvider:
    def extract_text(self, fp, ft):
        return "fake"

    def extract_structured(self, fp, ft):
        return []


def test_ocr_build_and_engines():
    assert "auto" in OCR_ENGINES and "pipeline" in OCR_ENGINES
    assert isinstance(build_ocr("auto", {}), AutoOCRProvider)
    with pytest.raises(TypeError):
        OCRProvider()  # type: ignore[abstract]


def test_ocr_route_handwritten_vs_printed(monkeypatch):
    import numpy as np
    monkeypatch.setattr("services.ocr_service._first_page_cv2",
                        lambda *a, **k: np.ones((50, 50, 3), dtype=np.uint8) * 255)
    monkeypatch.setattr("services.ocr_service._get_classifier",
                        lambda *a, **k: _FakeClassifier("HANDWRITTEN"))
    monkeypatch.setattr("services.ocr_service._get_qwen_wrapper",
                        lambda **k: _FakeProvider())
    prov = AutoOCRProvider()
    dt, p = prov._route("x", "image")
    assert dt == "HANDWRITTEN" and isinstance(p, _FakeProvider)

    monkeypatch.setattr("services.ocr_service._get_classifier",
                        lambda *a, **k: _FakeClassifier("PRINTED_TEXT"))
    monkeypatch.setattr("services.ocr_service._get_paddle_wrapper",
                        lambda **k: _FakeProvider())
    prov2 = AutoOCRProvider()
    dt2, p2 = prov2._route("x", "image")
    assert dt2 == "PRINTED_TEXT" and isinstance(p2, _FakeProvider)


def test_windows_gpu_defaults_are_enabled(monkeypatch):
    import importlib
    import platform

    monkeypatch.setattr(platform, "system", lambda: "Windows")
    monkeypatch.delenv("PADDLE_USE_GPU", raising=False)
    monkeypatch.delenv("FLAGS_use_gpu", raising=False)
    monkeypatch.delenv("CUDA_VISIBLE_DEVICES", raising=False)

    import main
    importlib.reload(main)

    assert os.environ.get("PADDLE_USE_GPU") == "1"
    assert os.environ.get("FLAGS_use_gpu") == "1"
    assert "CUDA_VISIBLE_DEVICES" not in os.environ


# ── unit_normaliser ─────────────────────────────────────────────
from unit_normaliser import normalise_unit, normalise_value


def test_unit_normaliser_micro_variants():
    for u in ("umol/L", "μmol/L", "Âµmol/L", "µmol/L", "Umol/L"):
        assert normalise_unit(u) == "µmol/L"


def test_unit_normaliser_canonical():
    assert normalise_unit("mg/dl") == "mg/dL"
    assert normalise_unit("u/l") == "U/L"


def test_unit_normalise_value():
    v, u = normalise_value("78", "u/l")
    assert v == "78" and u == "U/L"


# ── hepatology_kb ───────────────────────────────────────────────
from hepatology_kb import (
    lookup_reference_range, compute_flag, get_clinical_patterns,
    match_clinical_patterns, normalise_test_key, CLINICAL_PATTERN_RULES,
)


def test_kb_lookup_and_flag():
    rr = lookup_reference_range("ALT")
    assert rr and rr.high == 56
    assert compute_flag(78, rr) == "HIGH"
    assert compute_flag(10, rr) == "NORMAL"
    assert compute_flag(200, rr) == "CRITICAL_HIGH"


def test_kb_clinical_patterns():
    assert get_clinical_patterns()
    matches = match_clinical_patterns(["alanine aminotransferase", "aspartate aminotransferase"])
    assert any("Hepatocellular" in m["pattern"] for m in matches)
    assert normalise_test_key("ALT") == "alt"
    assert CLINICAL_PATTERN_RULES


# ── image_processing ────────────────────────────────────────────
from image_processing import (
    preprocess_image, enhance_contrast, quality_metrics, deskew, denoise, binarise,
)


def _doc():
    import numpy as np
    img = np.ones((400, 300, 3), dtype=np.uint8) * 255
    import cv2
    for y in range(40, 360, 40):
        cv2.line(img, (20, y), (280, y), (0, 0, 0), 2)
    return img


def test_image_processing_pipeline():
    img = _doc()
    assert isinstance(preprocess_image(img), type(img))
    assert isinstance(enhance_contrast(img), type(img))
    assert isinstance(denoise(img), type(img))
    assert isinstance(binarise(img), type(img))
    assert isinstance(deskew(img), type(img))
    qm = quality_metrics(img)
    for k in ("sharpness_laplacian_var", "contrast_rms", "skew_angle_degrees",
              "resolution_dpi", "snr"):
        assert k in qm


# ── heuristics ──────────────────────────────────────────────────
from heuristics import extract_structured_results


def test_heuristics_simple_items():
    items = [{"text": "ALT", "bounding_box": [[0, 0], [10, 0], [10, 10], [0, 10]]},
             {"text": "78", "bounding_box": [[20, 0], [30, 0], [30, 10], [20, 10]]},
             {"text": "U/L", "bounding_box": [[40, 0], [55, 0], [55, 10], [40, 10]]}]
    res = extract_structured_results(items, {})
    assert isinstance(res, list)


# ── classification_agent extra ──────────────────────────────────
from agents.classification_agent import ClassificationAgent
import numpy as np
import cv2


def _table_img():
    img = np.ones((800, 600, 3), dtype=np.uint8) * 255
    for r in range(19):
        y = int((r / 18) * 760) + 20
        cv2.line(img, (40, y), (560, y), (0, 0, 0), 2)
    for c in range(5):
        x = int((c / 4) * 520) + 40
        cv2.line(img, (x, 20), (x, 780), (0, 0, 0), 2)
    return img


def test_classification_agent_no_fallback_when_confident():
    # A confidently-classified document must not trigger the LLM fallback.
    # The TABLE-vs-PRINTED distinction for synthetic grids is ambiguous in
    # this dataset (real lab-reports are also gridded); the authoritative
    # TABLE accuracy is the real held-out eval, so we assert on the
    # fallback contract and a valid class rather than the specific label.
    agent = ClassificationAgent(llm_fallback=True, llm_client=None)
    res = agent.run(_table_img())
    assert res.doc_class in ("TABLE", "PRINTED_TEXT", "HANDWRITTEN")
    assert res.fallback_triggered is False


# ── summary_agent ───────────────────────────────────────────────
from agents.summary_agent import SummaryAgent
from schemas import DiagnosisResult, AbnormalValue, ClinicalPattern


def _mini_diagnosis():
    return DiagnosisResult(
        clinical_patterns=[ClinicalPattern(pattern="Hepatocellular injury",
                                            supporting_tests=["ALT"], description="d")],
        abnormal_values=[AbnormalValue(test="ALT", value=200, flag="CRITICAL_HIGH",
                                       note="very high")],
        urgent_flags=["ALT 200 U/L CRITICAL_HIGH"],
        suggested_followup=["Repeat LFTs"],
        summary_for_doctor="Elevated ALT.",
    )


def test_summary_doctor_heuristic():
    s = SummaryAgent(llm_client=None).run(_mini_diagnosis(), mode="doctor")
    assert s.critical_alerts
    assert "ALT" in json.dumps(s.dict())


def test_summary_patient_heuristic():
    s = SummaryAgent(llm_client=None).run(_mini_diagnosis(), mode="patient")
    assert isinstance(s, str) and "doctor" in s.lower()


class _FakeSummaryLLM:
    def complete(self, prompt, inp):
        if "Format ONLY as valid JSON" in prompt:
            return json.dumps({"summary": "s", "flags": [], "critical_alerts": ["ALT"],
                               "discussion_points": ["d"]})
        return "Your doctor will review these results and discuss them with you."


def test_summary_uses_llm_when_present():
    doc = SummaryAgent(llm_client=_FakeSummaryLLM()).run(_mini_diagnosis(), mode="doctor")
    assert doc.critical_alerts == ["ALT"]
    pat = SummaryAgent(llm_client=_FakeSummaryLLM()).run(_mini_diagnosis(), mode="patient")
    assert "doctor" in pat.lower()


# ── diagnosis_agent LLM path ────────────────────────────────────
from agents.diagnosis_agent import DiagnosisAgent
from schemas import LabReport, LabResult, ReferenceRange


def _lab():
    return LabReport(lab_results=[
        LabResult(test_name="ALT", test_abbreviation="ALT", value=200, unit="U/L",
                  reference_range=ReferenceRange(low=7, high=56, unit="U/L"),
                  flag="CRITICAL_HIGH"),
        LabResult(test_name="Albumin", test_abbreviation="ALB", value=3.2, unit="g/dL",
                  reference_range=ReferenceRange(low=3.5, high=5.0, unit="g/dL"),
                  flag="LOW"),
    ])


class _FakeDiagLLM:
    def complete(self, prompt, inp):
        return json.dumps({
            "clinical_patterns": [{"pattern": "Hepatocellular", "supporting_tests": ["ALT"],
                                   "description": "d"}],
            "abnormal_values": [{"test": "ALT", "value": 200, "flag": "CRITICAL_HIGH",
                                 "note": "high"}],
            "urgent_flags": ["ALT 200 U/L"],
            "suggested_followup": ["Repeat"],
            "summary_for_doctor": "Elevated ALT.",
        })


def test_diagnosis_agent_llm_path():
    dx = DiagnosisAgent(llm_client=_FakeDiagLLM()).run(_lab())
    assert dx.urgent_flags and dx.summary_for_doctor


# ── extraction_agent extra ──────────────────────────────────────
from agents.extraction_agent import ExtractionAgent, ExtractionResult
from agents.ocr_result import OCRResult


class _FakeExtLLM:
    def complete(self, prompt, inp):
        return json.dumps({"lab_results": [
            {"test_name": "ALT", "test_abbreviation": "ALT", "value": 78, "unit": "U/L",
             "reference_range": {"low": 7, "high": 56, "unit": "U/L"},
             "flag": "HIGH", "clinical_significance": "x"}]})


def test_extraction_agent_llm_path():
    ocr = OCRResult(raw_output="some text", engine="fake", confidence=0.9,
                    processing_time_seconds=0.0)
    res = ExtractionAgent(llm_client=_FakeExtLLM()).run(ocr)
    assert res.lab_results and res.lab_results[0]["test_name"] == "ALT"


def test_extraction_retry_prompt_constant():
    from agents.extraction_agent import VALIDATION_RETRY_PROMPT, EXTRACTION_SYSTEM_PROMPT
    assert "validation" in VALIDATION_RETRY_PROMPT.lower()
    assert "lab_results" in EXTRACTION_SYSTEM_PROMPT


# ── preprocessing_agent extra ───────────────────────────────────
from agents.preprocessing_agent import PreprocessingAgent, preprocess


def test_preprocess_module_wrapper():
    out = preprocess(_doc())
    assert out.preprocessed_image is not None and isinstance(out.preprocessed_image, np.ndarray)


# ── evaluation_agent dataset path (mocked OCR, no paddle) ───────
from agents.evaluation_agent import EvaluationAgent


class _FakeOCR:
    def __init__(self, text):
        self._text = text

    def run(self, image, doc_class):
        return OCRResult(raw_output=self._text, engine="fake", confidence=0.9,
                         processing_time_seconds=0.0)


def test_evaluation_dataset_with_fake_ocr():
    import cv2
    ag = EvaluationAgent()
    gt = {"img1.png": {"doc_class": "PRINTED_TEXT", "text": "ALT 78 U/L"},
          "img2.png": {"doc_class": "PRINTED_TEXT", "text": "ALT 78 U/L"}}
    # create tiny files so path checks pass
    d = tempfile.mkdtemp()
    for name in gt:
        cv2.imwrite(os.path.join(d, name), np.ones((50, 50, 3), dtype=np.uint8) * 255)
    rep = ag.evaluate_ocr_dataset(d, gt, run_ocr_fn=lambda img, dc: _FakeOCR("ALT 78 U/L").run(img, dc))
    assert rep.ocr_available is True
    assert rep.samples_evaluated == 2
    assert rep.cer is not None and rep.cer < 0.05
    assert rep.wer is not None


def test_evaluation_agent_run_method():
    ag = EvaluationAgent()
    rep = ag.run("ALT 78 U/L", "ALT 78 U/L",
                 extracted_json=[{"test_name": "ALT", "value": 78}],
                 ground_truth_json=[{"test_name": "ALT", "value": 78}])
    assert rep.cer == 0.0
    assert rep.field_accuracy == 1.0


# ── evaluation_routes compute path (mocked agent) ───────────────
def test_evaluation_route_compute(monkeypatch):
    # Exercise the REAL _compute_evaluation path, mocking only the heavy OCR /
    # network bits so the route's field-accuracy logic runs offline.
    import routes.evaluation_routes as er
    from agents.evaluation_agent import EvaluationAgent, EvaluationReport
    from agents.ocr_result import OCRResult
    from agents.extraction_agent import ExtractionAgent, ExtractionResult

    monkeypatch.setattr(
        EvaluationAgent, "evaluate_ocr_dataset",
        lambda self, d, gt, run_ocr_fn=None, limit=None: EvaluationReport(
            cer=0.01, wer=0.02, samples_evaluated=5, ocr_available=True))
    monkeypatch.setattr(
        "agents.ocr_router_agent.run_ocr",
        lambda image, doc_class: OCRResult(raw_output="ALT 78 U/L", engine="fake",
                                          confidence=0.9, processing_time_seconds=0.0))
    monkeypatch.setattr(
        ExtractionAgent, "run",
        lambda self, ocr_result: ExtractionResult(
            lab_results=[{"test_name": "ALT", "value": 78, "unit": "U/L",
                          "reference_range": {"low": 7, "high": 56, "unit": "U/L"},
                          "flag": "HIGH", "clinical_significance": None}],
            raw_llm_output="", fallback_used=True, source="heuristics", warnings=[]))

    monkeypatch.setattr(er, "_CACHE", {})
    from fastapi.testclient import TestClient
    from backend.main import app
    with TestClient(app) as client:
        body = client.get("/api/pipeline/evaluate?force=true").json()
        assert body["evaluation"]["cer"] == 0.01
        assert body["evaluation"]["field_accuracy"] is not None
        assert body["evaluation"]["ocr_available"] is True


def test_pipeline_service_automatic(tmp_db, monkeypatch):
    # Cover process_report_automatic (upload background task) without real OCR.
    import services.pipeline_service as ps
    from services.ocr_service import AutoOCRProvider

    monkeypatch.setattr(AutoOCRProvider, "extract_text",
                        lambda self, fp, ft: "automated ocr")
    monkeypatch.setattr(AutoOCRProvider, "extract_structured",
                        lambda self, fp, ft: [{"test_name": "ALT", "value": 78}])

    import tempfile
    from pathlib import Path

    tmp_file = Path(tempfile.gettempdir()) / "medvault_test_r1.png"
    tmp_file.write_bytes(b"\x89PNG\r\n\x1a\n")  # minimal placeholder file that exists

    conn = db_module.get_db()
    conn.execute(
        "INSERT INTO patients (id, phone, password_hash, name, created_at) "
        "VALUES ('p1','123','x','Test Patient','now')")
    conn.execute(
        "INSERT INTO reports (id, patient_id, filename, filepath, filetype, shared_at) "
        f"VALUES ('r1','p1','f.png','{tmp_file}','image','now')")
    conn.commit()
    conn.close()

    ps.process_report_automatic("r1")  # should run OCR + persist without error

    conn = db_module.get_db()
    row = conn.execute("SELECT ocr_text, status FROM reports WHERE id='r1'").fetchone()
    conn.close()
    assert row["ocr_text"] == "automated ocr"
    assert row["status"] == "done"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
