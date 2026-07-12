"""
tests/test_diagnosis_agent.py — Session 5 validation (offline / fast).

Covers:
  1. CRITICAL_HIGH ALT (>168 U/L) -> urgent_flags non-empty + test in abnormal_values
  2. Multi-abnormal report (ALT+AST+ALP) -> clinical_patterns populated
  3. LLM-free run (llm_client=None) -> populated DiagnosisResult, no exception
  4. SummaryAgent doctor output has critical_alerts; patient output is non-JSON str
  5. Pydantic DiagnosisResult rejects malformed input (missing field / wrong type)
"""
import json
import os
import sys

import pytest
from pydantic import ValidationError

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from schemas import (
    AbnormalValue,
    ClinicalPattern,
    DiagnosisResult,
    LabReport,
    LabResult,
    ReferenceRange,
    SummaryResponse,
)
from agents.diagnosis_agent import DiagnosisAgent
from agents.summary_agent import SummaryAgent


# ── Fake LLM (mirrors test_extraction_agent.FakeLLM) ─────────────

class FakeLLM:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0

    def complete(self, prompt, input):
        self.calls += 1
        idx = min(self.calls - 1, len(self._responses) - 1)
        return self._responses[idx]


def _result(name, value, flag, unit="U/L", low=None, high=None):
    return LabResult(
        test_name=name,
        test_abbreviation=name.split()[0] if " " in name else name,
        value=value,
        unit=unit,
        reference_range=ReferenceRange(low=low, high=high, unit=unit),
        flag=flag,
    )


def _report(results):
    return LabReport(lab_results=results)


# ── 1. CRITICAL_HIGH ALT -> urgent_flags ────────────────────────

def test_critical_high_alt_sets_urgent_flags():
    # 3x upper limit of ALT (56) -> 168; use 200 to be safely CRITICAL_HIGH.
    rep = _report([_result("Alanine Aminotransferase", 200.0, "CRITICAL_HIGH",
                           low=7.0, high=56.0)])
    dx = DiagnosisAgent(llm_client=None).run(rep)

    assert dx.urgent_flags, "CRITICAL_HIGH should populate urgent_flags"
    assert any("ALT" in f or "Alanine" in f for f in dx.urgent_flags)
    tests = [av.test for av in dx.abnormal_values]
    assert "Alanine Aminotransferase" in tests


# ── 2. Multi-abnormal -> clinical_patterns ──────────────────────

def test_multi_abnormal_has_clinical_patterns():
    rep = _report([
        _result("Alanine Aminotransferase", 200.0, "CRITICAL_HIGH", low=7.0, high=56.0),
        _result("Aspartate Aminotransferase", 80.0, "HIGH", low=10.0, high=40.0),
        _result("Alkaline Phosphatase", 200.0, "HIGH", low=44.0, high=147.0),
    ])
    dx = DiagnosisAgent(llm_client=None).run(rep)

    patterns = [p.pattern for p in dx.clinical_patterns]
    assert patterns, "expected at least one clinical pattern"
    assert "Hepatocellular injury pattern" in patterns
    assert "Cholestatic pattern" in patterns
    assert dx.suggested_followup  # heuristics suggest follow-up


# ── 3. LLM-free run populates DiagnosisResult ───────────────────

def test_llm_free_run_populates_result():
    rep = _report([
        _result("ALT", 120.0, "HIGH", low=7.0, high=56.0),
        _result("Albumin", 2.8, "LOW", low=3.5, high=5.0, unit="g/dL"),
    ])
    dx = DiagnosisAgent(llm_client=None).run(rep)

    assert isinstance(dx, DiagnosisResult)
    assert dx.abnormal_values
    assert dx.llm_narrative is None
    assert dx.summary_for_doctor


# ── 4. SummaryAgent doctor/patient ──────────────────────────────

def test_summary_agent_doctor_has_critical_alerts():
    rep = _report([_result("Alanine Aminotransferase", 200.0, "CRITICAL_HIGH",
                           low=7.0, high=56.0)])
    dx = DiagnosisAgent(llm_client=None).run(rep)
    summary = SummaryAgent(llm_client=None).run(dx, mode="doctor")

    assert isinstance(summary, SummaryResponse)
    assert summary.critical_alerts == dx.urgent_flags
    assert summary.critical_alerts


def test_summary_agent_patient_is_nonjson_string():
    rep = _report([_result("Alanine Aminotransferase", 200.0, "CRITICAL_HIGH",
                           low=7.0, high=56.0)])
    dx = DiagnosisAgent(llm_client=None).run(rep)
    out = SummaryAgent(llm_client=None).run(dx, mode="patient")

    assert isinstance(out, str)
    assert not out.strip().startswith("{")
    with pytest.raises(json.JSONDecodeError):
        json.loads(out)


# ── 5. Pydantic validation rejects malformed DiagnosisResult ────

def test_diagnosis_result_rejects_missing_field():
    with pytest.raises(ValidationError):
        DiagnosisResult(
            clinical_patterns=[],
            abnormal_values=[],
            urgent_flags=[],
            suggested_followup=[],
            # summary_for_doctor omitted -> required
        )


def test_diagnosis_result_rejects_wrong_type():
    with pytest.raises(ValidationError):
        DiagnosisResult(
            clinical_patterns="not-a-list",
            abnormal_values=[],
            urgent_flags=[],
            suggested_followup=[],
            summary_for_doctor="x",
        )


# ── Bonus: LLM path parses into DiagnosisResult ─────────────────

def test_diagnosis_agent_uses_llm_when_present():
    llm_json = json.dumps({
        "clinical_patterns": [
            {"pattern": "Hepatocellular injury pattern",
             "supporting_tests": ["ALT", "AST"], "description": "d"}
        ],
        "abnormal_values": [
            {"test": "ALT", "value": 200.0, "flag": "CRITICAL_HIGH", "note": "n"}
        ],
        "urgent_flags": ["ALT 200 U/L (CRITICAL_HIGH)"],
        "suggested_followup": ["repeat LFTs"],
        "summary_for_doctor": "Elevated ALT.",
    })
    rep = _report([_result("Alanine Aminotransferase", 200.0, "CRITICAL_HIGH",
                           low=7.0, high=56.0)])
    dx = DiagnosisAgent(llm_client=FakeLLM([llm_json])).run(rep)

    assert dx.llm_narrative
    assert dx.clinical_patterns[0].pattern == "Hepatocellular injury pattern"
    assert dx.urgent_flags == ["ALT 200 U/L (CRITICAL_HIGH)"]
