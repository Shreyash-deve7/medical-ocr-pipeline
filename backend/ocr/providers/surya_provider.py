"""Surya OCR wrapper for table and handwritten fallback.

CRITICAL: ``DETECTOR_BATCH_SIZE`` is forced to ``1`` at module import time
to prevent GPU OOM when Surya's detector runs with its default larger batch size.
"""

import os

# CRITICAL: limit Surya detector batch size to avoid OOM on 8 GB VRAM.
os.environ.setdefault("DETECTOR_BATCH_SIZE", "1")

from typing import Any, Dict

import numpy as np


def _extract_table(image: np.ndarray) -> Dict[str, Any]:
    """Run Surya table extraction if the package is installed."""
    try:
        from surya.ocr import OcrModel
        from surya.table import TableRecognitionModel

        # Lazy-load models to avoid VRAM bloat at startup
        if not hasattr(_extract_table, "_ocr_model"):
            _extract_table._ocr_model = OcrModel()
            _extract_table._table_model = TableRecognitionModel()

        result = _extract_table._table_model.predict([image])
        return {
            "table": result[0].html if result else [],
            "confidence": result[0].confidence if result else 0.0,
            "engine": "SuryaOCR",
        }
    except Exception:
        return {"table": [], "confidence": 0.0, "engine": "fallback_empty"}


def _extract_handwritten(image: np.ndarray) -> Dict[str, Any]:
    """Run Surya OCR for handwritten text if the package is installed."""
    try:
        from surya.ocr import OcrModel

        if not hasattr(_extract_handwritten, "_ocr_model"):
            _extract_handwritten._ocr_model = OcrModel()

        result = _extract_handwritten._ocr_model.predict([image])
        texts = [line.text for line in result[0].lines] if result else []
        return {
            "text": texts,
            "confidence": result[0].avg_confidence if result else 0.0,
            "engine": "SuryaOCR",
        }
    except Exception:
        return {"text": [], "confidence": 0.0, "engine": "fallback_empty"}
