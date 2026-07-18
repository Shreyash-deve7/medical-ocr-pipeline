"""
router.py — Unified OCR dispatcher.

Routes a preprocessed image to the correct OCR engine based on document class.
This is the single entry point for all OCR operations.
"""
import time
from typing import Dict, Any

import numpy as np

from .ocr1_table import extract_table
from .ocr2_handwritten import extract_handwritten
from .ocr3_printed import extract_printed_text


def run_ocr(preprocessed_image: np.ndarray, doc_class: str) -> Dict[str, Any]:
    """
    Route image to the correct OCR engine based on doc_class.

    Args:
        preprocessed_image: Preprocessed image as numpy array (BGR).
        doc_class: One of 'TABLE', 'HANDWRITTEN', 'PRINTED_TEXT'.

    Returns:
        {
            "doc_class": str,
            "ocr_engine_used": str,
            "raw_output": str or list[list[str]],
            "processing_time_seconds": float,
            "confidence": float (optional)
        }
    """
    t0 = time.time()

    dispatch = {
        "TABLE": extract_table,
        "HANDWRITTEN": extract_handwritten,
        "PRINTED_TEXT": extract_printed_text,
    }

    if doc_class not in dispatch:
        raise ValueError(f"Unknown doc_class: {doc_class!r}. Expected one of {list(dispatch.keys())}")

    result = dispatch[doc_class](preprocessed_image)

    return {
        "doc_class": doc_class,
        "raw_output": result.get("text") or result.get("table", ""),
        "ocr_engine_used": result.get("engine", "unknown"),
        "processing_time_seconds": round(time.time() - t0, 2),
        "confidence": result.get("confidence", None),
    }