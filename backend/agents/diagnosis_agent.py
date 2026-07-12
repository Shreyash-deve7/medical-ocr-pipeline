"""
diagnosis_agent.py — Agent 6 of the MedVault agentic pipeline.

Applies the Hepatology knowledge base (``hepatology_kb``) to a validated
:class:`LabReport` to surface abnormal values, group them into clinical
patterns, flag CRITICAL values requiring urgent attention, and suggest
follow-up — all as decision-support only (no final diagnosis, no treatment).

The agent is LLM-first but always degrades to a deterministic rule-based
engine so it works with no LLM client configured (``llm_client=None``) and
never crashes the pipeline.

LLM client contract (pluggable, mirroring classification_agent.py /
extraction_agent.py):
    client.complete(prompt: str, input: str) -> str

Only depends on standard library + backend modules, so it is unit-testable
offline with a fake client.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Set

from loguru import logger

import hepatology_kb
from hepatology_kb import (
    lookup_reference_range,
    match_clinical_patterns,
    normalise_test_key,
)
from schemas import (
    AbnormalValue,
    ClinicalPattern,
    DiagnosisResult,
    LabReport,
)

# Flags that indicate a value is outside normal limits.
_ABNORMAL_FLAGS = {"HIGH", "LOW", "CRITICAL_HIGH", "CRITICAL_LOW"}
_CRITICAL_FLAGS = {"CRITICAL_HIGH", "CRITICAL_LOW"}

# Follow-up suggestions keyed by clinical-pattern name.
_PATTERN_FOLLOWUP = {
    "Hepatocellular injury pattern": [
        "Repeat liver function tests in 2-4 weeks to trend ALT/AST",
        "Consider viral hepatitis panel (Hep A/B/C) and autoimmune screen",
    ],
    "Cholestatic pattern": [
        "Abdominal ultrasound to assess the biliary tree",
        "Consider MRCP if ALP/GGT elevations persist",
    ],
    "Synthetic dysfunction": [
        "Review coagulation; repeat PT/INR",
        "Assess for chronic liver disease / cirrhosis",
    ],
    "Hyperbilirubinemia": [
        "Fractionate bilirubin (direct vs indirect)",
        "Assess for hemolysis versus hepatobiliary cause",
    ],
}


DIAGNOSIS_SYSTEM_PROMPT = """You are a hepatology clinical decision support assistant.

Below are validated lab results from a patient's liver function test. You have access
to AASLD reference ranges and Sherlock's Diseases of the Liver terminology.

LAB RESULTS (validated JSON):
{lab_results_json}

Your task:
1. Identify ALL abnormal values (HIGH, LOW, CRITICAL_HIGH, CRITICAL_LOW)
2. Group related abnormalities into clinical patterns (e.g., "Hepatocellular injury pattern")
3. List possible differentials based ONLY on the lab values
   (do NOT diagnose — state possibilities only)
4. Flag values requiring URGENT attention (CRITICAL range)
5. Suggest follow-up tests if patterns are ambiguous

Respond ONLY with valid JSON:
{
  "clinical_patterns": [
    {"pattern": "...", "supporting_tests": [...], "description": "..."}
  ],
  "abnormal_values": [
    {"test": "...", "value": ..., "flag": "...", "note": "..."}
  ],
  "urgent_flags": ["..."],
  "suggested_followup": ["..."],
  "summary_for_doctor": "2-3 sentence plain English summary"
}

IMPORTANT: This is a clinical DECISION SUPPORT tool only.
Do NOT make a final diagnosis. Do NOT suggest specific treatments.
"""


class DiagnosisAgent:
    """Agent 6 — rule-based Hepatology diagnosis support with LLM enhancement."""

    def __init__(self, llm_client=None):
        """
        :param llm_client: pluggable client exposing
            ``complete(prompt: str, input: str) -> str``. If ``None`` the agent
            uses the deterministic rule-based engine and emits a WARNING.
        """
        self.llm_client = llm_client

    # ── Public API ──────────────────────────────────────────────────

    def run(self, lab_report: LabReport) -> DiagnosisResult:
        """Produce a :class:`DiagnosisResult` for ``lab_report``."""
        if self.llm_client is None:
            logger.warning("No LLM client configured; using rule-based diagnosis engine")
            return self._rule_based(lab_report)

        try:
            formatted = self._format_input(lab_report)
            raw = self.llm_client.complete(DIAGNOSIS_SYSTEM_PROMPT, formatted)
            return self._parse_llm(raw)
        except Exception as e:
            logger.warning("LLM diagnosis failed ({}); using rule-based fallback", e)
            return self._rule_based(lab_report)

    # ── LLM parsing ────────────────────────────────────────────────

    def _parse_llm(self, raw: str) -> DiagnosisResult:
        """Parse an LLM JSON response into a validated DiagnosisResult."""
        data = _parse_json_object(raw)
        if data is None:
            raise ValueError("LLM diagnosis response contained no JSON object")
        try:
            return DiagnosisResult(
                clinical_patterns=[
                    ClinicalPattern(**p) for p in data.get("clinical_patterns", [])
                ],
                abnormal_values=[
                    AbnormalValue(**a) for a in data.get("abnormal_values", [])
                ],
                urgent_flags=list(data.get("urgent_flags", [])),
                suggested_followup=list(data.get("suggested_followup", [])),
                summary_for_doctor=data.get("summary_for_doctor", ""),
                llm_narrative=raw,
            )
        except Exception as e:
            raise ValueError(f"LLM diagnosis JSON failed validation: {e}")

    def _format_input(self, lab_report: LabReport) -> str:
        """Render the validated lab results as JSON for the LLM prompt."""
        return json.dumps(
            [lr.model_dump() for lr in lab_report.lab_results], ensure_ascii=False
        )

    # ── Rule-based engine ──────────────────────────────────────────

    def _rule_based(self, lab_report: LabReport) -> DiagnosisResult:
        """Deterministic Hepatology diagnosis from the KB."""
        abnormal: List[AbnormalValue] = []
        urgent: List[str] = []
        abnormal_keys: Set[str] = set()

        for lr in lab_report.lab_results:
            if lr.flag not in _ABNORMAL_FLAGS:
                continue
            note = lr.clinical_significance
            if not note:
                ref = lookup_reference_range(lr.test_name)
                if ref is not None:
                    note = f"Reference range {ref.low}-{ref.high} {ref.unit}"
            abnormal.append(
                AbnormalValue(
                    test=lr.test_name,
                    value=lr.value,
                    flag=lr.flag,
                    note=note,
                )
            )
            abnormal_keys.add(normalise_test_key(lr.test_name))
            if lr.flag in _CRITICAL_FLAGS:
                unit = lr.unit or ""
                val = f"{lr.value} {unit}".strip()
                urgent.append(f"{lr.test_name} {val} ({lr.flag})")

        patterns = [
            ClinicalPattern(**p) for p in match_clinical_patterns(abnormal_keys)
        ]
        followup = self._build_followup(patterns)
        summary = self._build_summary(patterns, urgent, abnormal)

        return DiagnosisResult(
            clinical_patterns=patterns,
            abnormal_values=abnormal,
            urgent_flags=urgent,
            suggested_followup=followup,
            summary_for_doctor=summary,
            llm_narrative=None,
        )

    @staticmethod
    def _build_followup(patterns: List[ClinicalPattern]) -> List[str]:
        """Collect de-duplicated follow-up suggestions from matched patterns."""
        out: List[str] = []
        seen = set()
        for p in patterns:
            for sug in _PATTERN_FOLLOWUP.get(p.pattern, []):
                if sug not in seen:
                    seen.add(sug)
                    out.append(sug)
        if not out:
            out.append("Correlate abnormal values with clinical context and repeat testing as indicated")
        return out

    @staticmethod
    def _build_summary(patterns: List[ClinicalPattern], urgent: List[str],
                       abnormal: List[AbnormalValue]) -> str:
        """Compose a 2-3 sentence plain-English summary for the doctor."""
        if not abnormal:
            return "All reviewed laboratory values are within normal limits."
        parts = [f"{len(abnormal)} abnormal liver-function value(s) identified"]
        if patterns:
            names = ", ".join(p.pattern for p in patterns)
            parts.append(f"consistent with a {names.lower()}" if len(patterns) == 1
                         else f"consistent with {names}")
        summary = ". ".join(parts) + "."
        if urgent:
            summary += (" URGENT: " + "; ".join(urgent) +
                        " require prompt clinical attention.")
        return summary


def _parse_json_object(raw: str) -> Optional[Dict[str, Any]]:
    """Best-effort parse of an LLM JSON response. Returns dict or None."""
    if not raw:
        return None
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not m:
            return None
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            return None
