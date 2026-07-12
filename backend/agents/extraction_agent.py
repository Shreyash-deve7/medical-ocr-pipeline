"""
extraction_agent.py — Agent 4 of the MedVault agentic pipeline.

Converts a uniform :class:`OCRResult` (from the OCR Router) into a list of
lab-result dicts conforming to the IBM spec §6.4 ``lab_results`` schema.

The agent is LLM-first but degrades gracefully: when no pluggable LLM client is
available (or the LLM returns unparseable JSON and retries are exhausted) it
falls back to the existing ``heuristics.extract_structured_results`` and emits a
WARNING — it never crashes the pipeline.

LLM client contract (pluggable, see classification_agent.py for the pattern):
    client.complete(prompt: str, input: str) -> str

Only depends on standard library + the existing backend modules so it is
unit-testable offline with a fake client.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from loguru import logger

from agents.ocr_result import OCRResult
from hepatology_kb import lookup_reference_range, compute_flag
from schemas import LabReport
from unit_normaliser import normalise_unit

EXTRACTION_MAX_RETRIES = 1

EXTRACTION_SYSTEM_PROMPT = """You are a medical data extraction assistant specialised in Hepatology lab reports.

Given the raw OCR text below, extract ALL laboratory test results and return ONLY
a valid JSON object conforming exactly to this schema:

{
  "lab_results": [
    {
      "test_name": <full test name as appears in report>,
      "test_abbreviation": <abbreviation if present, else null>,
      "value": <numeric value as float>,
      "unit": <unit string — normalise to SI units where possible>,
      "reference_range": { "low": <float|null>, "high": <float|null>, "unit": <string> },
      "flag": <"HIGH" | "LOW" | "CRITICAL_HIGH" | "CRITICAL_LOW" | "NORMAL" | "UNKNOWN">,
      "clinical_significance": <one-sentence clinical note relevant to liver/hepatology>
    }
  ]
}

RULES:
- Units: use U/L for enzymes (ALT, AST, ALP, GGT); g/dL for Hb/Albumin;
  mg/dL for Bilirubin/Creatinine; µmol/L for Ammonia; seconds for PT; INR is unitless
- If a value is absent in the text, use null. Do NOT invent values.
- CRITICAL_HIGH if value > 3× upper reference limit
- CRITICAL_LOW if value < 0.5× lower reference limit
- For TABLE input: first row is headers; subsequent rows are data
- For HANDWRITTEN/PRINTED input: parse line-by-line for test/value/unit patterns
- Output ONLY valid JSON — no markdown fences, no preamble, no explanation

RAW OCR OUTPUT:
{ocr_raw_text}
"""

VALIDATION_RETRY_PROMPT = """The previous extraction attempt failed Pydantic validation with these errors:
{validation_errors}

The raw OCR input was:
{ocr_raw_text}

The failed JSON output was:
{failed_json}

Fix ONLY the fields listed in the validation errors. Do not change fields that were valid.
Return ONLY the corrected JSON with no preamble or markdown.
"""


@dataclass
class ExtractionResult:
    """Raw extraction output before Pydantic validation."""

    lab_results: List[Dict[str, Any]]
    raw_llm_output: str = ""
    fallback_used: bool = False
    source: str = "llm"
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "lab_results": self.lab_results,
            "raw_llm_output": self.raw_llm_output,
            "fallback_used": self.fallback_used,
            "source": self.source,
            "warnings": self.warnings,
        }


class ExtractionAgent:
    """Agent 4 — OCR -> lab-result dicts via LLM with heuristic fallback."""

    def __init__(self, llm_client=None):
        """
        :param llm_client: pluggable client exposing
            ``complete(prompt: str, input: str) -> str``. If ``None`` the agent
            skips the LLM entirely and uses the heuristic fallback.
        """
        self.llm_client = llm_client

    # ── Public API ──────────────────────────────────────────────────

    def run(self, ocr_result: OCRResult) -> ExtractionResult:
        """Extract lab results from ``ocr_result`` -> :class:`ExtractionResult`."""
        formatted = self._format_input(ocr_result)

        if self.llm_client is None:
            logger.warning("No LLM client configured; using heuristic extraction fallback")
            return self._heuristics_fallback(ocr_result, "no-llm-client")

        raw = self._call_llm_with_retry(EXTRACTION_SYSTEM_PROMPT, formatted)
        parsed = self._parse_json(raw)
        if parsed is not None:
            return self._finalise(parsed, raw, fallback_used=False, source="llm")

        # LLM returned unparseable JSON and retries were exhausted -> fallback.
        logger.warning("LLM extraction returned invalid JSON; falling back to heuristics")
        return self._heuristics_fallback(ocr_result, "invalid-json")

    def retry(self, ocr_result: OCRResult, prev_result: ExtractionResult,
              validation_errors: Any) -> ExtractionResult:
        """
        Re-attempt extraction feeding validation errors back to the LLM.

        Used by ValidationAgent (Agent 5) when Pydantic validation fails. Returns
        ``prev_result`` unchanged when no LLM client is configured (cannot retry).
        """
        if self.llm_client is None:
            logger.warning("Validation retry requested but no LLM client; keeping previous result")
            return prev_result

        formatted = self._format_input(ocr_result)
        errors_text = json.dumps(validation_errors) if not isinstance(validation_errors, str) \
            else validation_errors
        prompt = VALIDATION_RETRY_PROMPT.format(
            validation_errors=errors_text,
            ocr_raw_text=formatted,
            failed_json=prev_result.raw_llm_output or json.dumps(prev_result.lab_results),
        )
        raw = self._call_llm_with_retry(prompt, formatted)
        parsed = self._parse_json(raw)
        if parsed is not None:
            return self._finalise(parsed, raw, fallback_used=False, source="llm-retry")
        # Retry also failed to parse; keep the prior (invalid) result so the
        # ValidationAgent can surface the original error rather than crashing.
        return prev_result

    # ── Internals ───────────────────────────────────────────────────

    def _call_llm_with_retry(self, prompt: str, formatted_input: str) -> str:
        """Call ``llm.complete``; retry on JSONDecodeError up to MAX_RETRIES."""
        last_err: Optional[Exception] = None
        for attempt in range(EXTRACTION_MAX_RETRIES + 1):
            try:
                raw = self.llm_client.complete(prompt, formatted_input)
            except Exception as e:  # LLM transport failure
                last_err = e
                logger.warning("LLM complete() failed (attempt {}): {}", attempt, e)
                continue
            if self._parse_json(raw) is not None:
                return raw
            last_err = ValueError("LLM returned non-JSON output")
            logger.warning("LLM returned unparseable JSON (attempt {}); retrying", attempt)
        if last_err:
            logger.warning("LLM extraction exhausted retries: {}", last_err)
        return raw if "raw" in dir() else ""

    def _parse_json(self, raw: str) -> Optional[Dict[str, Any]]:
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

    def _finalise(self, parsed: Dict[str, Any], raw: str,
                  fallback_used: bool, source: str) -> ExtractionResult:
        """Normalise units / attach KB reference ranges + flags, build result."""
        results = parsed.get("lab_results", []) if isinstance(parsed, dict) else []
        cleaned: List[Dict[str, Any]] = []
        for item in results:
            if not isinstance(item, dict):
                continue
            unit = normalise_unit(item.get("unit", ""))
            item["unit"] = unit
            rr = item.get("reference_range")
            if not isinstance(rr, dict):
                ref = lookup_reference_range(item.get("test_name", ""))
                rr = ref.model_dump() if ref else {"low": None, "high": None, "unit": unit}
            else:
                rr = {
                    "low": rr.get("low"),
                    "high": rr.get("high"),
                    "unit": normalise_unit(rr.get("unit", unit) or unit),
                }
            item["reference_range"] = rr
            if item.get("flag") in (None, "UNKNOWN") and item.get("value") is not None:
                ref_obj = lookup_reference_range(item.get("test_name", ""))
                item["flag"] = compute_flag(item.get("value"), ref_obj)
            cleaned.append(item)
        return ExtractionResult(
            lab_results=cleaned,
            raw_llm_output=raw,
            fallback_used=fallback_used,
            source=source,
        )

    def _format_input(self, ocr_result: OCRResult) -> str:
        """Render OCRResult.raw_output as text for the LLM prompt."""
        raw = ocr_result.raw_output
        if isinstance(raw, list):
            # TABLE 2D output: render as a grid, first row = headers.
            if not raw:
                return "(empty table)"
            return "\n".join(" | ".join(str(c) for c in row) for row in raw)
        if isinstance(raw, str):
            return raw.strip() or "(empty)"
        return str(raw)

    # ── Heuristic fallback ──────────────────────────────────────────

    def _heuristics_fallback(self, ocr_result: OCRResult, reason: str) -> ExtractionResult:
        """Use heuristics.extract_structured_results as a graceful fallback."""
        from heuristics import extract_structured_results

        items = self._build_ocr_items(ocr_result)
        config = self._load_medical_rules()
        try:
            structured = extract_structured_results(items, config)
        except Exception as e:
            logger.warning("Heuristic extraction failed: {}; returning empty results", e)
            return ExtractionResult(
                lab_results=[],
                raw_llm_output="",
                fallback_used=True,
                source="heuristics",
                warnings=[f"heuristics-error:{e}", reason],
            )

        lab_results: List[Dict[str, Any]] = []
        for he in structured:
            canonical = (he.get("test_name") or {}).get("normalized") or \
                (he.get("test_name") or {}).get("raw_ocr") or ""
            val = (he.get("value") or {}).get("normalized_value")
            unit = (he.get("value") or {}).get("unit") or ""
            unit = normalise_unit(unit)
            rng = he.get("reference_range") or {}
            ref = lookup_reference_range(canonical)
            if ref is not None:
                low, high = ref.low, ref.high
                rr_unit = ref.unit
            else:
                low, high = rng.get("min"), rng.get("max")
                rr_unit = unit or "unitless"
            rr = {
                "low": low if low is not None else None,
                "high": high if high is not None else None,
                "unit": normalise_unit(rr_unit),
            }
            flag = compute_flag(val, ref)
            lab_results.append({
                "test_name": canonical,
                "test_abbreviation": None,
                "value": val if isinstance(val, (int, float)) else None,
                "unit": unit or rr_unit,
                "reference_range": rr,
                "flag": flag,
                "clinical_significance": None,
            })

        return ExtractionResult(
            lab_results=lab_results,
            raw_llm_output="",
            fallback_used=True,
            source="heuristics",
            warnings=[reason],
        )

    def _build_ocr_items(self, ocr_result: OCRResult) -> List[Dict[str, Any]]:
        """
        Build OCR item dicts (text + bbox) consumable by heuristics.

        TABLE 2D -> one item per cell, rows share a y so group_ocr_into_lines
        keeps them together. str -> one item per whitespace token, lines share y.
        Synthetic bboxes let the heuristic y-clustering work without real coords.
        """
        items: List[Dict[str, Any]] = []
        raw = ocr_result.raw_output
        y = 10.0
        if isinstance(raw, list):
            for row in raw:
                x = 10.0
                cells = row if isinstance(row, (list, tuple)) else [row]
                for cell in cells:
                    text = str(cell).strip()
                    if not text:
                        x += 20.0
                        continue
                    items.append(self._make_item(text, x, y))
                    x += 20.0
                y += 20.0
        elif isinstance(raw, str):
            for line in raw.splitlines():
                x = 10.0
                for token in line.split():
                    items.append(self._make_item(token, x, y))
                    x += 20.0
                y += 20.0
        return items

    @staticmethod
    def _make_item(text: str, x: float, y: float) -> Dict[str, Any]:
        return {
            "text": text,
            "bounding_box": [
                [x, y], [x + 10, y], [x + 10, y + 10], [x, y + 10],
            ],
            "confidence": 1.0,
        }

    @staticmethod
    def _load_medical_rules() -> Dict[str, Any]:
        path = os.path.join(os.path.dirname(__file__), "..", "backend", "medical_rules.json")
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            # Fallback: resolve relative to cwd if running from backend/.
            try:
                with open("medical_rules.json", "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning("Could not load medical_rules.json: {}", e)
                return {"test_name_mappings": {}, "correction_rules": {}}
