"""
table_ocr_agent.py — Agent 3a of the MedVault agentic pipeline.

Extracts 2D table structure from TABLE-class documents.

Primary path : PaddleOCR PP-Structure (table recovery) via
               ``PaddleOCRProvider.extract_table_pp_structure``.
Fallback path: basic PaddleOCR (``run_paddle_ocr_on_document``) with heuristic
               y-clustering row grouping, used when PP-Structure confidence is
               below ``confidence_threshold`` (default 0.75) or is unavailable.

The providers operate on filepaths, so the input ``ndarray`` is transiently
written to a temp PNG. Heavy PaddleOCR / PP-Structure imports are lazy and the
provider instances are injectable for offline unit testing.
"""
from __future__ import annotations

import os
import tempfile
import time
from typing import List, Optional

import cv2
import numpy as np
from loguru import logger

from agents.ocr_result import OCRResult

_PP_STRUCTURE_ENGINE = "PaddleOCR-PP-Structure"
_FALLBACK_ENGINE = "PaddleOCR-Basic-Fallback"
_CONFIDENCE_THRESHOLD = 0.75


def _save_tmp(image: np.ndarray) -> str:
    """Write a BGR ndarray to a temp PNG and return its path (caller deletes)."""
    fd, path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    ok = cv2.imwrite(path, image)
    if not ok:
        raise IOError("Failed to write temporary image for OCR agent")
    return path


def _group_lines_into_rows(lines: List[dict], y_tolerance: int = 15) -> List[List[str]]:
    """
    Group reading-ordered OCR line dicts (each with ``text`` and ``bbox``) into
    rows using the vertical centre of each bbox. Returns a 2D list of strings.
    """
    if not lines:
        return []
    indexed = []
    for ln in lines:
        bbox = ln.get("bbox") or [[0, 0]]
        ys = [p[1] for p in bbox]
        yc = sum(ys) / len(ys)
        indexed.append((yc, ln.get("text", "")))
    indexed.sort(key=lambda t: t[0])
    rows: List[List[str]] = []
    current_y = None
    for yc, text in indexed:
        if current_y is None or abs(yc - current_y) > y_tolerance:
            rows.append([])
            current_y = yc
        rows[-1].append(text)
    return rows


class TableOCRAgent:
    """Agent 3a — TABLE OCR via PaddleOCR PP-Structure with basic-OCR fallback."""

    def __init__(self, pp_provider=None, paddle_provider=None,
                 confidence_threshold: float = _CONFIDENCE_THRESHOLD):
        self._pp_provider = pp_provider
        self._paddle_provider = paddle_provider
        self.confidence_threshold = float(confidence_threshold)

    @property
    def pp_provider(self):
        if self._pp_provider is None:
            from paddle_ocr_provider import PaddleOCRProvider
            self._pp_provider = PaddleOCRProvider()
        return self._pp_provider

    @property
    def paddle_provider(self):
        if self._paddle_provider is None:
            from paddle_ocr_provider import PaddleOCRProvider
            self._paddle_provider = PaddleOCRProvider()
        return self._paddle_provider

    def run(self, image: np.ndarray) -> OCRResult:
        """Extract a 2D table from ``image`` (BGR ndarray) -> OCRResult."""
        start = time.time()
        tmp = _save_tmp(image)
        try:
            # ── Primary: PP-Structure ──────────────────────────────────────────
            try:
                rows = self.pp_provider.extract_table_pp_structure(tmp, "image")
                if rows:
                    conf = self.pp_provider.table_confidence(rows)
                    if conf >= self.confidence_threshold:
                        return OCRResult(
                            raw_output=rows,
                            engine=_PP_STRUCTURE_ENGINE,
                            confidence=conf,
                            processing_time_seconds=time.time() - start,
                        )
                    logger.info(
                        "PP-Structure confidence {:.2f} < {:.2f}; using fallback",
                        conf, self.confidence_threshold,
                    )
            except Exception as e:
                logger.warning("PP-Structure path failed, falling back: {}", e)

            # ── Fallback: basic PaddleOCR + heuristic row grouping ─────────────
            from paddle_ocr_provider import run_paddle_ocr_on_document
            lines = run_paddle_ocr_on_document(
                tmp, use_gpu=self.paddle_provider.use_gpu,
                lang=self.paddle_provider.lang,
                use_angle_cls=self.paddle_provider.use_angle_cls,
                target_max_dim=self.paddle_provider.target_max_dim,
                min_conf=self.paddle_provider.min_conf,
            )
            rows = _group_lines_into_rows(lines)
            confs = [ln.get("confidence", 0.0) for ln in lines]
            conf = round(float(sum(confs) / len(confs)), 4) if confs else 0.5
            return OCRResult(
                raw_output=rows,
                engine=_FALLBACK_ENGINE,
                confidence=conf if conf > 0 else 0.5,
                processing_time_seconds=time.time() - start,
            )
        finally:
            try:
                os.remove(tmp)
            except OSError:
                pass
