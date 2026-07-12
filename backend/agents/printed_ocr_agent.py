"""
printed_ocr_agent.py — Agent 3c of the MedVault agentic pipeline.

Extracts text from printed/typed medical documents using a fallback chain:

    1. PaddleOCR (basic text mode)        -> engine "PaddleOCR-Basic"
    2. Tesseract 5 (optional, if present) -> engine "Tesseract-5"
    3. empty                              -> engine "none", confidence 0.0

Tesseract is an **optional** link: if ``pytesseract`` (or the ``tesseract``
binary) is unavailable we skip it gracefully and fall through to the next step,
never raising. The PaddleOCR provider is injectable for offline unit testing.
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

_ENGINE_PADDLE = "PaddleOCR-Basic"
_ENGINE_TESSERACT = "Tesseract-5"
_ENGINE_NONE = "none"


def _tesseract_available() -> bool:
    """Return True only if pytesseract + a tesseract binary are importable/runnable."""
    try:
        import pytesseract  # noqa: F401
        import shutil
        return shutil.which("tesseract") is not None
    except Exception:
        return False


class PrintedOCRAgent:
    """Agent 3c — printed OCR via PaddleOCR with optional Tesseract fallback."""

    def __init__(self, paddle_provider=None):
        self._paddle_provider = paddle_provider

    @property
    def paddle_provider(self):
        if self._paddle_provider is None:
            from paddle_ocr_provider import PaddleOCRProvider
            self._paddle_provider = PaddleOCRProvider()
        return self._paddle_provider

    def run(self, image: np.ndarray) -> OCRResult:
        """OCR a printed ``image`` (BGR ndarray) -> first non-empty engine result."""
        start = time.time()
        fd, tmp = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        try:
            ok = cv2.imwrite(tmp, image)
            if not ok:
                raise IOError("Failed to write temporary image for printed OCR")

            # ── 1. PaddleOCR (basic) ───────────────────────────────────────────
            try:
                text = self.paddle_provider.extract_text(tmp, "image")
                if text and text.strip():
                    return OCRResult(
                        raw_output=text,
                        engine=_ENGINE_PADDLE,
                        confidence=0.9,
                        processing_time_seconds=time.time() - start,
                    )
            except Exception as e:
                logger.warning("PaddleOCR printed path failed: {}", e)

            # ── 2. Tesseract (optional) ───────────────────────────────────────
            if _tesseract_available():
                try:
                    import pytesseract
                    t_text = pytesseract.image_to_string(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
                    if t_text and t_text.strip():
                        return OCRResult(
                            raw_output=t_text,
                            engine=_ENGINE_TESSERACT,
                            confidence=0.7,
                            processing_time_seconds=time.time() - start,
                        )
                except Exception as e:
                    logger.warning("Tesseract printed path failed: {}", e)

            # ── 3. Nothing extracted ───────────────────────────────────────────
            return OCRResult(
                raw_output="",
                engine=_ENGINE_NONE,
                confidence=0.0,
                processing_time_seconds=time.time() - start,
            )
        finally:
            try:
                os.remove(tmp)
            except OSError:
                pass
