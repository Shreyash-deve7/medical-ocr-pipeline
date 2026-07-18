""" ocr2_handwritten.py — Handwritten OCR via Qwen2.5-VL (primary) or Surya (fallback). Uses local provider implementations under ``backend/ocr/providers/``. """
import numpy as np
from typing import Any, Dict

from .providers.qwen_provider import QwenVLProvider
from .providers.surya_provider import _extract_handwritten


def extract_handwritten(image: np.ndarray) -> Dict[str, Any]:
    """ Extract handwritten text using Qwen2.5-VL (primary) or Surya (fallback). Returns: { "text": str, "confidence": float, "engine": str } """
    # Try Qwen2.5-VL
    try:
        provider = QwenVLProvider()
        text = provider.extract_text(image, "image")
        if text and text.strip():
            return {
                "text": text.strip(),
                "confidence": 0.90,
                "engine": "Qwen2.5-VL",
            }
    except Exception:
        pass

    # Fallback: Surya (handwriting mode)
    return _extract_handwritten(image)