"""
formatter.py — LLM-based formatting of raw OCR text into structured JSON.

This module provides the ``format_with_llm`` function that takes raw OCR output
and uses an LLM to transform it into the structured lab_results JSON format
defined in the IBM spec §6.3.

The LLM call is a placeholder (``_call_llm``) that currently returns empty
results. Replace the implementation with your actual LLM client (Watsonx,
OpenAI, or local Granite) when ready.
"""
import json
import os
from typing import Dict, Any

from loguru import logger


def format_with_llm(raw_ocr_text: str, doc_class: str) -> Dict[str, Any]:
    """
    Format raw OCR text into structured JSON using LLM.

    Args:
        raw_ocr_text: Raw text from OCR engine.
        doc_class: Document class (TABLE / HANDWRITTEN / PRINTED_TEXT).

    Returns:
        {
            "lab_results": [
                {
                    "test_name": str,
                    "test_abbreviation": str | None,
                    "value": float | None,
                    "unit": str,
                    "reference_range": {"low": float, "high": float, "unit": str},
                    "flag": str,
                    "clinical_significance": str | None
                }
            ]
        }
    """
    api_key = os.getenv("LLM_API_KEY")
    if not api_key:
        logger.warning("LLM_API_KEY not set; returning empty results")
        return {"lab_results": []}

    system_prompt = _get_system_prompt()
    user_prompt = f"OCR OUTPUT ({doc_class}):\n{raw_ocr_text}"

    try:
        response = _call_llm(system_prompt, user_prompt, api_key)
        result = json.loads(response)
        return result
    except Exception as e:
        logger.error(f"LLM formatting failed: {e}")
        return {"lab_results": []}


def _get_system_prompt() -> str:
    return """You are a medical data extraction assistant specialised in Hepatology lab reports.

Given the raw OCR text below, extract all laboratory test results and return ONLY
a valid JSON object conforming exactly to this schema:

{
    "lab_results": [
        {
            "test_name": <full test name as appears in report>,
            "test_abbreviation": <abbreviation if present, else null>,
            "value": <numeric value as float>,
            "unit": <unit string — normalise to SI units where possible>,
            "reference_range": {"low": <float|null>, "high": <float|null>, "unit": <string>},
            "flag": <"HIGH" | "LOW" | "CRITICAL_HIGH" | "CRITICAL_LOW" | "NORMAL" | "UNKNOWN">,
            "clinical_significance": <one-sentence clinical note relevant to liver/hepatology>
        }
    ]
}

Rules:
- For units: use U/L for enzymes, g/dL for haemoglobin/albumin, mg/dL for bilirubin/creatinine, µmol/L for ammonia
- If a value is not present in the text, use null
- Do NOT invent values
- Flags: mark CRITICAL_HIGH if value > 3× upper reference limit
"""


def _call_llm(system_prompt: str, user_prompt: str, api_key: str) -> str:
    """
    Call LLM; returns JSON string.

    TODO: Implement actual LLM call (Watsonx, OpenAI, or local Granite).
    For now: placeholder that returns empty results.
    """
    # Placeholder — replace with actual LLM integration
    return json.dumps({"lab_results": []})