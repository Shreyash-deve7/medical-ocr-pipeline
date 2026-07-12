"""
handwritten_ocr_agent.py — Agent 3b of the MedVault agentic pipeline.

Transcribes handwritten medical text using Qwen2.5-VL (via ``qwen_vl_provider``).

The QwenVLProvider is **lazy-instantiated** inside ``run()`` (never at import or
construction) because its constructor raises without a CUDA GPU or a
``server_url`` — this keeps the agent importable and unit-testable on CPU-only
CI where a fake provider is injected instead.
"""
from __future__ import annotations

import os
import tempfile
import time
from typing import Optional

import cv2
import numpy as np
from loguru import logger

from agents.ocr_result import OCRResult

_ENGINE = "Qwen2.5-VL"
_DEFAULT_CONFIDENCE = 0.8


class HandwrittenOCRAgent:
    """Agent 3b — handwritten OCR via Qwen2.5-VL."""

    def __init__(self, provider=None, confidence: float = _DEFAULT_CONFIDENCE):
        self._provider = provider
        self.confidence = float(confidence)

    @property
    def provider(self):
        if self._provider is None:
            from qwen_vl_provider import QwenVLProvider
            self._provider = QwenVLProvider()
        return self._provider

    def run(self, image: np.ndarray) -> OCRResult:
        """Transcribe ``image`` (BGR ndarray) -> OCRResult with raw text."""
        start = time.time()
        fd, tmp = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        try:
            ok = cv2.imwrite(tmp, image)
            if not ok:
                raise IOError("Failed to write temporary image for handwritten OCR")
            text = self.provider.extract_text(tmp, "image")
            return OCRResult(
                raw_output=text or "",
                engine=_ENGINE,
                confidence=self.confidence,
                processing_time_seconds=time.time() - start,
            )
        finally:
            try:
                os.remove(tmp)
            except OSError:
                pass
