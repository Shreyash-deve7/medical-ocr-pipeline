"""
summary_agent.py — Agent 8 of the MedVault agentic pipeline.

Generates a doctor-facing structured summary or a patient-facing plain-English
summary from a :class:`DiagnosisResult`. The prompts formalise the existing
summary intent from ``main.py`` (``MEDICAL_PROMPT``) into the reference.md
Section E Agent 8 contract.

The agent is LLM-first but always has a deterministic heuristic fallback so it
works with no LLM client (``llm_client=None``) and never crashes.

LLM client contract (pluggable, mirroring the other agents):
    client.complete(prompt: str, input: str) -> str

Only depends on standard library + backend modules, so it is unit-testable
offline with a fake client.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from loguru import logger

from hepatology_kb import lookup_reference_range
from schemas import DiagnosisResult, SummaryResponse


SUMMARY_DOCTOR_PROMPT = """You are assisting a licensed medical professional reviewing a patient's lab report.
Do NOT make diagnoses. Do NOT suggest treatments.

Your role:
- Summarize the key findings in 3-5 sentences
- List values outside normal reference ranges with their clinical significance
- Highlight any CRITICAL values requiring immediate attention
- Provide 3 concise discussion points for the doctor-patient conversation

Format ONLY as valid JSON — no markdown fences:
{
  "summary": "...",
  "flags": [{"field": "...", "value": ..., "normal_range": "...", "note": "..."}],
  "critical_alerts": ["..."],
  "discussion_points": ["..."]
}

MEDICAL DATA:
{diagnosis_json}
"""

SUMMARY_PATIENT_PROMPT = """You are a friendly medical report assistant explaining lab results to a patient.
The patient has no medical background. Use plain English.
Do NOT use jargon without explaining it.
Do NOT make diagnoses or suggest treatments.
Always include: "Your doctor will review these results and discuss them with you."

MEDICAL DATA:
{diagnosis_json}

Respond in 3-4 plain sentences. No JSON. No bullet lists.
"""


class SummaryAgent:
    """Agent 8 — doctor/patient summary generation from a DiagnosisResult."""

    def __init__(self, llm_client=None):
        """
        :param llm_client: pluggable client exposing
            ``complete(prompt: str, input: str) -> str``. If ``None`` the agent
            uses the deterministic heuristic summariser and emits a WARNING.
        """
        self.llm_client = llm_client

    # ── Public API ──────────────────────────────────────────────────

    def run(self, diagnosis: DiagnosisResult, mode: str = "doctor"):
        """
        Generate a summary.

        :param diagnosis: the :class:`DiagnosisResult` to summarise.
        :param mode: ``"doctor"`` (structured :class:`SummaryResponse`) or
            ``"patient"`` (plain-English ``str``, no JSON).
        :returns: :class:`SummaryResponse` for doctor mode, ``str`` for patient.
        """
        if mode == "patient":
            return self._run_patient(diagnosis)
        return self._run_doctor(diagnosis)

    # ── Doctor mode ─────────────────────────────────────────────────

    def _run_doctor(self, diagnosis: DiagnosisResult) -> SummaryResponse:
        if self.llm_client is None:
            logger.warning("No LLM client configured; using heuristic doctor summary")
            return self._heuristic_doctor(diagnosis)
        try:
            formatted = json.dumps(diagnosis.model_dump(), ensure_ascii=False)
            raw = self.llm_client.complete(SUMMARY_DOCTOR_PROMPT, formatted)
            return self._parse_llm_doctor(raw)
        except Exception as e:
            logger.warning("LLM doctor summary failed ({}); heuristic fallback", e)
            return self._heuristic_doctor(diagnosis)

    def _parse_llm_doctor(self, raw: str) -> SummaryResponse:
        data = _parse_json_object(raw)
        if data is None:
            raise ValueError("LLM doctor summary contained no JSON object")
        return SummaryResponse(
            summary=data.get("summary", ""),
            flags=list(data.get("flags", [])),
            critical_alerts=list(data.get("critical_alerts", [])),
            discussion_points=list(data.get("discussion_points", [])),
        )

    def _heuristic_doctor(self, diagnosis: DiagnosisResult) -> SummaryResponse:
        flags: List[Dict[str, Any]] = []
        for av in diagnosis.abnormal_values:
            ref = lookup_reference_range(av.test)
            normal_range = (
                f"{ref.low}-{ref.high} {ref.unit}" if ref else "n/a"
            )
            flags.append({
                "field": av.test,
                "value": av.value,
                "normal_range": normal_range,
                "note": av.note or "",
            })

        patterns = [p.pattern for p in diagnosis.clinical_patterns]
        discussion = []
        if patterns:
            discussion.append(
                "Review the " + ", ".join(patterns).lower() +
                " with the patient and correlate with symptoms."
            )
        if diagnosis.suggested_followup:
            discussion.append(
                "Consider follow-up: " +
                "; ".join(diagnosis.suggested_followup) + "."
            )
        discussion.append(
            "Reinforce that these results are decision-support and require "
            "clinical correlation by the treating physician."
        )

        return SummaryResponse(
            summary=diagnosis.summary_for_doctor or "See abnormal values below.",
            flags=flags,
            critical_alerts=list(diagnosis.urgent_flags),
            discussion_points=discussion[:3] if discussion else [
                "Discuss abnormal values with the patient."
            ],
        )

    # ── Patient mode ────────────────────────────────────────────────

    def _run_patient(self, diagnosis: DiagnosisResult) -> str:
        if self.llm_client is None:
            logger.warning("No LLM client configured; using heuristic patient summary")
            return self._heuristic_patient(diagnosis)
        try:
            formatted = json.dumps(diagnosis.model_dump(), ensure_ascii=False)
            return self.llm_client.complete(SUMMARY_PATIENT_PROMPT, formatted)
        except Exception as e:
            logger.warning("LLM patient summary failed ({}); heuristic fallback", e)
            return self._heuristic_patient(diagnosis)

    def _heuristic_patient(self, diagnosis: DiagnosisResult) -> str:
        abnormal = [av for av in diagnosis.abnormal_values]
        if not abnormal:
            body = "Your liver function tests came back within the normal range."
        else:
            names = ", ".join(av.test for av in abnormal)
            body = (
                f"Some of your liver function tests were outside the usual range "
                f"({names}). This does not mean anything is seriously wrong on its "
                f"own — these results are one piece of your overall health picture."
            )
        if diagnosis.urgent_flags:
            body += (
                " A few results are marked as needing prompt review by your care "
                "team."
            )
        body += " Your doctor will review these results and discuss them with you."
        return body


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
