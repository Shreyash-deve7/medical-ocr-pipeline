"""
tests/test_extraction_agent.py — Session 4 validation (offline / fast).

Covers:
  1. Pydantic LabReport / LabResult schema (accept valid, reject malformed)
  2. ExtractionAgent with a fake LLM client returning known JSON
  3. ExtractionAgent graceful degradation on invalid JSON (retry + fallback)
  4. ValidationAgent 2-retry: invalid-then-valid LLM output -> valid LabReport
  5. unit_normaliser µ-encoding fix round-trips
  6. hepatology_kb reference-range lookup
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from schemas import LabReport, LabResult, ReferenceRange
from hepatology_kb import lookup_reference_range, compute_flag
from unit_normaliser import normalise_unit
from agents.ocr_result import OCRResult
from agents.extraction_agent import ExtractionAgent, ExtractionResult
from agents.validation_agent import ValidationAgent


# ── Fixtures ───────────────────────────────────────────────────────

class FakeLLM:
    """Pluggable fake LLM client. By default returns valid JSON once, then a
    second distinct payload on retry. Can be configured to return invalid JSON
    or a bad-flag payload for the validation-retry scenario."""

    def __init__(self, responses):
        # responses: list of strings returned in order per complete() call.
        self._responses = list(responses)
        self.calls = 0

    def complete(self, prompt, input):
        self.calls += 1
        idx = min(self.calls - 1, len(self._responses) - 1)
        return self._responses[idx]


def _valid_json():
    return (
        '{"lab_results": ['
        '{"test_name": "Alanine Aminotransferase", "test_abbreviation": "ALT",'
        '"value": 78.0, "unit": "U/L",'
        '"reference_range": {"low": 7.0, "high": 56.0, "unit": "U/L"},'
        '"flag": "HIGH", "clinical_significance": "Elevated ALT"}'
        ']}'
    )


def _bad_flag_json():
    # Valid JSON, but an invalid flag enum -> ValidationError downstream.
    return (
        '{"lab_results": ['
        '{"test_name": "ALT", "test_abbreviation": "ALT",'
        '"value": 78.0, "unit": "U/L",'
        '"reference_range": {"low": 7.0, "high": 56.0, "unit": "U/L"},'
        '"flag": "SUPER_HIGH", "clinical_significance": "x"}'
        ']}'
    )


# ── 1. Pydantic schema ─────────────────────────────────────────────

def test_labreport_accepts_valid_sample():
    rep = LabReport(lab_results=[
        LabResult(
            test_name="ALT",
            test_abbreviation="ALT",
            value=78.0,
            unit="U/L",
            reference_range=ReferenceRange(low=7.0, high=56.0, unit="U/L"),
            flag="HIGH",
            clinical_significance="Elevated",
        )
    ])
    assert rep.lab_results[0].flag == "HIGH"
    assert rep.lab_results[0].value == 78.0


def test_labreport_rejects_missing_required_field():
    with pytest.raises(Exception):
        LabReport(lab_results=[
            LabResult(
                unit="U/L",
                reference_range=ReferenceRange(low=7.0, high=56.0, unit="U/L"),
                flag="HIGH",
            )
        ])


def test_labresult_rejects_bad_flag_enum():
    with pytest.raises(Exception):
        LabResult(
            test_name="ALT",
            unit="U/L",
            reference_range=ReferenceRange(low=7.0, high=56.0, unit="U/L"),
            flag="NOT_A_FLAG",
        )


# ── 2. ExtractionAgent with known JSON ─────────────────────────────

def test_extraction_agent_parses_valid_json():
    client = FakeLLM([_valid_json()])
    agent = ExtractionAgent(llm_client=client)
    ocr = OCRResult(raw_output="ALT 78 U/L", engine="PaddleOCR-Basic",
                    confidence=0.9, processing_time_seconds=0.1)
    res = agent.run(ocr)
    assert isinstance(res, ExtractionResult)
    assert len(res.lab_results) == 1
    assert res.lab_results[0]["test_name"] == "Alanine Aminotransferase"
    # Should validate into a LabReport.
    report = LabReport(lab_results=res.lab_results)
    assert report.lab_results[0].flag == "HIGH"


# ── 3. Graceful degradation on invalid JSON ───────────────────────

def test_extraction_agent_retries_then_falls_back_on_invalid_json():
    client = FakeLLM(["not json at all", "still not json"])
    agent = ExtractionAgent(llm_client=client)
    ocr = OCRResult(raw_output="ALT 78 U/L", engine="PaddleOCR-Basic",
                    confidence=0.9, processing_time_seconds=0.1)
    res = agent.run(ocr)  # must NOT raise
    assert client.calls >= 2  # retry happened
    assert res.fallback_used is True
    assert res.source == "heuristics"
    assert isinstance(res, ExtractionResult)


def test_extraction_agent_falls_back_without_llm():
    agent = ExtractionAgent(llm_client=None)
    ocr = OCRResult(raw_output="ALT 78 U/L", engine="PaddleOCR-Basic",
                    confidence=0.9, processing_time_seconds=0.1)
    res = agent.run(ocr)
    assert res.fallback_used is True
    assert res.source == "heuristics"


# ── 4. ValidationAgent 2-retry (bad flag -> valid) ─────────────────

def test_validation_agent_retries_on_bad_flag():
    # First complete() returns bad-flag JSON (ValidationError), second returns
    # the corrected valid JSON.
    client = FakeLLM([_bad_flag_json(), _valid_json()])
    agent = ExtractionAgent(llm_client=client)
    validator = ValidationAgent(max_retries=2)
    ocr = OCRResult(raw_output="ALT 78 U/L", engine="PaddleOCR-Basic",
                    confidence=0.9, processing_time_seconds=0.1)
    extraction = agent.run(ocr)
    report = validator.run(extraction, ocr, agent)
    assert isinstance(report, LabReport)
    assert report.lab_results[0].flag == "HIGH"
    assert client.calls == 2  # one for run, one for retry


# ── 5. unit_normaliser µ round-trip ────────────────────────────────

@pytest.mark.parametrize("raw", ["umol/L", "Âµmol/L", "μmol/L", "µmol/L", "Umol/L"])
def test_unit_normaliser_micro_roundtrip(raw):
    assert normalise_unit(raw) == "µmol/L"


def test_unit_normaliser_canonical_cases():
    assert normalise_unit("mg/dl") == "mg/dL"
    assert normalise_unit("u/l") == "U/L"
    assert normalise_unit("g/dl") == "g/dL"
    assert normalise_unit("") == "unitless"


# ── 6. hepatology_kb lookup ────────────────────────────────────────

def test_kb_lookup_by_name_and_abbreviation():
    assert lookup_reference_range("ALT") == ReferenceRange(low=7.0, high=56.0, unit="U/L")
    assert lookup_reference_range("sgpt") == ReferenceRange(low=7.0, high=56.0, unit="U/L")
    assert lookup_reference_range("ALP") == ReferenceRange(low=44.0, high=147.0, unit="U/L")


def test_kb_lookup_ggt_sex_specific():
    male = lookup_reference_range("GGT", sex="M")
    female = lookup_reference_range("GGT", sex="F")
    assert male == ReferenceRange(low=8.0, high=61.0, unit="U/L")
    assert female == ReferenceRange(low=5.0, high=36.0, unit="U/L")


def test_kb_lookup_micro_unit():
    assert lookup_reference_range("ammonia") == ReferenceRange(low=15.0, high=45.0, unit="µmol/L")
    assert lookup_reference_range("NH3") == ReferenceRange(low=15.0, high=45.0, unit="µmol/L")


def test_kb_compute_flag_thresholds():
    alt = lookup_reference_range("ALT")
    # 3x upper = 168 -> CRITICAL_HIGH
    assert compute_flag(200.0, alt) == "CRITICAL_HIGH"
    assert compute_flag(78.0, alt) == "HIGH"
    assert compute_flag(20.0, alt) == "NORMAL"
    # 0.5x lower = 3.5 -> CRITICAL_LOW
    assert compute_flag(2.0, alt) == "CRITICAL_LOW"
    assert compute_flag(None, alt) == "UNKNOWN"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
