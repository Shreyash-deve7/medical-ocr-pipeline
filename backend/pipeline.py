"""
Core pipeline orchestrator for MedVault Hepatology OCR Pipeline.
Handles document classification and OCR routing.
"""
import os
import time
import re
from typing import Tuple, Optional
from enum import Enum
import numpy as np
from PIL import Image
import cv2


class DocumentClass(Enum):
    HANDWRITTEN = "HANDWRITTEN"
    PRINTED_TEXT = "PRINTED_TEXT"
    TABLE = "TABLE"


class AutoOCRProvider:
    """
    OCR Router that selects the appropriate engine based on document class.
    - HANDWRITTEN -> Qwen2.5-VL (4-bit quantized VLM)
    - PRINTED_TEXT / TABLE -> PaddleOCR (GPU-accelerated)
    """
    
    def __init__(self):
        self._qwen_engine = None
        self._paddle_engine = None
    
    def _get_qwen_engine(self):
        """Lazy-load Qwen2.5-VL engine with 4-bit quantization."""
        if self._qwen_engine is None:
            try:
                from engines.qwen_engine import QwenVLEngine
                self._qwen_engine = QwenVLEngine()
            except ImportError:
                raise RuntimeError(
                    "Qwen2.5-VL engine not available. "
                    "Ensure transformers, torch, and bitsandbytes are installed."
                )
        return self._qwen_engine
    
    def _get_paddle_engine(self):
        """Lazy-load PaddleOCR engine."""
        if self._paddle_engine is None:
            try:
                from engines.paddle_engine import PaddleOCREngine
                self._paddle_engine = PaddleOCREngine()
            except ImportError:
                raise RuntimeError(
                    "PaddleOCR engine not available. "
                    "Ensure paddlepaddle-gpu is installed with CUDA 12.9 support."
                )
        return self._paddle_engine
    
    def extract_text(self, image_path: str, doc_class: DocumentClass) -> Tuple[str, float]:
        """
        Route to appropriate OCR engine based on document class.
        
        Returns:
            Tuple of (extracted_text, duration_seconds)
        """
        start_time = time.time()
        
        if doc_class == DocumentClass.HANDWRITTEN:
            engine = self._get_qwen_engine()
            text = engine.extract_text(image_path)
        else:
            # PRINTED_TEXT or TABLE -> PaddleOCR
            engine = self._get_paddle_engine()
            if doc_class == DocumentClass.TABLE:
                text = engine.extract_table(image_path)
            else:
                text = engine.extract_text(image_path)
        
        duration = time.time() - start_time
        return text, duration



# NOTE: The 3-class DocumentClassifier (TABLE / HANDWRITTEN / PRINTED_TEXT)
# now lives in ``backend.classifier`` (modularised from the old
# ``document_classifier.py``). The OCR routing/provider logic used by the
# pipeline is in ``backend.services.ocr_service``. This module retains only the
# generic ``AutoOCRProvider`` helper above; the stale ``DocumentClassifier`` +
# singleton glue that previously lived here has been removed to avoid two
# divergent classifier implementations.
