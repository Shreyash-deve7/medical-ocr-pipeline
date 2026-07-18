"""
ocr1_table.py — Table OCR via PaddleOCR PP-Structure (primary) or Surya (fallback). Uses local provider implementations under ``backend/ocr/providers/``.
"""
import numpy as np
from typing import Any, Dict

from .providers.paddle_provider import PaddleOCRProvider
from .providers.surya_provider import _extract_table


def extract_table(image: np.ndarray) -> Dict[str, Any]:
    """ Extract table from image using PaddleOCR PP-Structure (primary) or Surya OCR (fallback), or return an empty table on complete failure.
    Returns: { "table": list[list[str]], # 2-D grid "confidence": float, "engine": str } """
    # Try PaddleOCR PP-Structure
    try:
        provider = PaddleOCRProvider()
        result = provider.extract_table_pp_structure(image)
        if result and isinstance(result, list):
            return {
                "table": result,
                "confidence": 0.95,
                "engine": "PaddleOCR-PP-Structure",
            }
    except Exception:
        pass

    # Fallback: Surya table extraction
    return _extract_table(image)