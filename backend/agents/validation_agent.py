"""
validation_agent.py — Agent 5 of the MedVault agentic pipeline.

Validates extracted lab results against the Pydantic :class:`LabReport` schema
and retries the ExtractionAgent (Agent 4) on failure, feeding validation errors
back via the validation retry prompt (reference.md Section E Agent 5).

Retry policy: up to ``MAX_RETRIES`` (default 2) corrections. If validation still
fails after exhausting retries, the final :class:`ValidationError` is raised so
the caller can decide how to handle an unrecoverable extraction.

Only depends on standard library + backend modules; unit-testable offline.
"""
from __future__ import annotations

import json
from typing import Any

from loguru import logger
from pydantic import ValidationError

from agents.extraction_agent import ExtractionResult
from agents.ocr_result import OCRResult
from schemas import LabReport


class ValidationAgent:
    """Agent 5 — Pydantic validation of LabReport with retry-on-failure."""

    MAX_RETRIES = 2

    def __init__(self, max_retries: int = MAX_RETRIES):
        self.max_retries = int(max_retries)

    def run(self, extraction_result: ExtractionResult, ocr_result: OCRResult,
            extraction_agent) -> LabReport:
        """
        Validate ``extraction_result`` into a :class:`LabReport`.

        On :class:`ValidationError`, ask ``extraction_agent.retry(...)`` for a
        corrected extraction (up to ``max_retries`` times) and re-validate.

        :raises ValidationError: if validation fails after all retries.
        """
        last_error: Any = None
        current = extraction_result
        for attempt in range(self.max_retries + 1):
            try:
                return LabReport(lab_results=current.lab_results)
            except ValidationError as e:
                last_error = e
                if attempt == self.max_retries:
                    logger.error("LabReport validation failed after {} retries", self.max_retries)
                    raise
                logger.warning(
                    "Validation attempt {} failed; requesting extraction retry", attempt
                )
                try:
                    current = extraction_agent.retry(
                        ocr_result, current, e.errors()
                    )
                except Exception as ex:
                    logger.warning("Extraction retry raised; aborting: {}", ex)
                    raise last_error
        # Should be unreachable; raise the last error for safety.
        raise last_error
