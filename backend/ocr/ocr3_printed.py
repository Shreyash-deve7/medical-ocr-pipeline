""" ocr3_printed.py — Printed text OCR routed strictly to the local PaddleOCR provider. Uses ``backend/ocr/providers/paddle_provider.py`` so the pipeline does not depend on extern submodules for the printed path. """
import numpy as np
from typing import Any, Dict

from .providers.paddle_provider import PaddleOCRProvider


def extract_printed_text(image: np.ndarray) -> Dict[str, Any]:
    """ Extract printed text using the local PaddleOCR provider. Returns: { "text": str, "confidence": float, "engine": str } """
    try:
        provider = PaddleOCRProvider()
        text = provider.extract_text(image, "image")
        if text and text.strip():
            return {
                "text": text.strip(),
                "confidence": 0.95,
                "engine": "PaddleOCR-Basic",
            }
    except Exception:
        pass

    return {"text": "", "confidence": 0.0, "engine": "fallback_empty"}