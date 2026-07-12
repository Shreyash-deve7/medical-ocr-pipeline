"""
ocr_result.py — Shared OCR output contract for the MedVault agentic pipeline.

Every OCR agent (Table / Handwritten / Printed) and the OCRRouterAgent return a
single, uniform :class:`OCRResult` so downstream stages (ExtractionAgent, etc.)
can consume OCR output without knowing which engine produced it.

Output contract (reference.md Section F / Session 3):
    OCRResult(raw_output, engine, confidence, processing_time_seconds)
"""
from dataclasses import dataclass, asdict
from typing import Any, Dict


@dataclass
class OCRResult:
    """
    Uniform OCR output.

    :param raw_output: OCR text (``str``) for HANDWRITTEN/PRINTED_TEXT routes, or
        a 2D ``list[list[str]]`` table for the TABLE (PP-Structure) route.
    :param engine: human-readable engine name, e.g. ``"PaddleOCR-PP-Structure"``,
        ``"Qwen2.5-VL"``, ``"PaddleOCR-Basic"``, ``"Tesseract-5"`` or ``"none"``.
    :param confidence: engine/route confidence in [0.0, 1.0].
    :param processing_time_seconds: wall-clock seconds spent in the route.
    """

    raw_output: Any
    engine: str
    confidence: float
    processing_time_seconds: float

    def to_dict(self) -> Dict[str, Any]:
        """Serialise all four contract fields for logging / JSON responses."""
        return {
            "raw_output": self.raw_output,
            "engine": self.engine,
            "confidence": round(float(self.confidence), 4),
            "processing_time_seconds": round(float(self.processing_time_seconds), 4),
        }
