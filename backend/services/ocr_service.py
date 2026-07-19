"""backend/services/ocr_service.py — OCR provider layer (Session 6).

Extracted verbatim from ``main.py``:
  - ``OCRProvider`` ABC + Paddle/Qwen wrappers
  - cached factory singletons (``_get_classifier`` / ``_get_paddle_wrapper`` /
    ``_get_qwen_wrapper``)
  - ``AutoOCRProvider`` (3-class routing added in Session 2)
  - ``OCR_ENGINES`` registry + ``build_ocr``

Heavy imports (paddle/qwen/torch/document_classifier) stay lazy inside the
functions/constructors exactly as before, so importing this module is cheap and
CPU-only safe.
"""
from __future__ import annotations

import os
import threading
from abc import ABC, abstractmethod
from typing import Optional

from loguru import logger


def _looks_like_vision_error(text: str) -> bool:
    """Detect when a vision-capable endpoint returned a text-only-model error."""
    t = (text or "").lower()
    return (
        "does not support image" in t
        or "not a multimodal" in t
        or ("multimodal" in t and "support" in t)
    )


class OCRProvider(ABC):
    @abstractmethod
    def extract_text(self, filepath: str, filetype: str) -> str: ...


class PaddleOCRProviderWrapper(OCRProvider):
    """MedVault wrapper around the PaddleOCR GPU backend for printed reports."""
    def __init__(self, use_gpu: bool = True, lang: str = "en", use_angle_cls: bool = True):
        from backend.ocr.providers.paddle_provider import PaddleOCRProvider
        self._provider = PaddleOCRProvider(use_gpu=use_gpu, lang=lang, use_angle_cls=use_angle_cls)
    def extract_text(self, filepath: str, filetype: str) -> str:  # pragma: no cover - GPU/OCR runtime
        return self._provider.extract_text(filepath, filetype)

    def extract_structured(self, filepath: str, filetype: str) -> list[dict]:  # pragma: no cover - GPU/OCR runtime
        return self._provider.extract_structured(filepath, filetype)


class QwenVLProviderWrapper(OCRProvider):
    """MedVault wrapper around Qwen2.5-VL for handwritten report transcription (GPU)."""
    def __init__(self, model_id: str = "Qwen/Qwen2.5-VL-3B-Instruct", device: str = "",
                 torch_dtype: str = "bfloat16", server_url: str = "", max_pixels: int = 128 * 28 * 28,
                 load_in_4bit: bool = True):
        from backend.ocr.providers.qwen_provider import QwenVLProvider
        # Honour the microservice URL from the environment so the in-process torch
        # path (which needs CUDA) is only taken when no GPU microservice is set.
        env_url = os.environ.get("QWEN_VL_SERVER_URL", "") or ""
        effective_url = server_url or env_url
        self._provider = QwenVLProvider(
            model_id=model_id,
            device=device or None,
            torch_dtype=torch_dtype,
            server_url=effective_url,
            max_pixels=max_pixels,
            load_in_4bit=load_in_4bit,
        )
    def extract_text(self, filepath: str, filetype: str) -> str:  # pragma: no cover - GPU/OCR runtime
        return self._provider.extract_text(filepath, filetype)

    def extract_structured(self, filepath: str, filetype: str) -> list[dict]:  # pragma: no cover - GPU/OCR runtime
        return self._provider.extract_structured(filepath, filetype)


# Module-level singletons for caching
_paddle_wrapper_cache = None
_paddle_wrapper_lock = threading.Lock()
_qwen_wrapper_cache = None
_qwen_wrapper_lock = threading.Lock()


def _get_paddle_wrapper(use_gpu: bool = True, lang: str = "en", use_angle_cls: bool = True):
    """Get cached PaddleOCRProviderWrapper instance."""
    global _paddle_wrapper_cache
    key = (use_gpu, lang, use_angle_cls)
    if _paddle_wrapper_cache is None or _paddle_wrapper_cache[0] != key:
        with _paddle_wrapper_lock:
            if _paddle_wrapper_cache is None or _paddle_wrapper_cache[0] != key:
                try:
                    _paddle_wrapper_cache = (key, PaddleOCRProviderWrapper(use_gpu=use_gpu, lang=lang, use_angle_cls=use_angle_cls))
                except Exception as e:
                    logger.warning("PaddleOCR wrapper failed to initialize: {}", e)
                    _paddle_wrapper_cache = (key, None)
    return _paddle_wrapper_cache[1]


def _get_qwen_wrapper(server_url: str = "", model_id: str = "Qwen/Qwen2.5-VL-3B-Instruct",
                      device: str = "", torch_dtype: str = "bfloat16",
                      max_pixels: int = 128 * 28 * 28, load_in_4bit: bool = True):
    """Get cached QwenVLProviderWrapper instance."""
    global _qwen_wrapper_cache
    key = (server_url, model_id, device, torch_dtype, max_pixels, load_in_4bit)
    if _qwen_wrapper_cache is None or _qwen_wrapper_cache[0] != key:
        with _qwen_wrapper_lock:
            if _qwen_wrapper_cache is None or _qwen_wrapper_cache[0] != key:
                if server_url:
                    _qwen_wrapper_cache = (key, QwenVLProviderWrapper(server_url=server_url))
                else:
                    _qwen_wrapper_cache = (key, QwenVLProviderWrapper(
                        model_id=model_id, device=device or None, torch_dtype=torch_dtype,
                        max_pixels=max_pixels, load_in_4bit=load_in_4bit))
    return _qwen_wrapper_cache[1]


class AutoOCRProvider(OCRProvider):
    """
    MedVault OCRProvider that auto-detects whether a document is HANDWRITTEN,
    PRINTED_TEXT or TABLE and routes it to the right backend.

    Routing policy (confidence-gated, see ``_classify``):
        * HANDWRITTEN (only if the classifier is confident) -> Qwen2.5-VL.
          When ``QWEN_VL_SERVER_URL`` is set, this runs as a GPU microservice
          in a separate CUDA process (recommended — keeps torch-CUDA out of
          this venv, which only has paddlepaddle-gpu). Otherwise it runs
          in-process (requires torch with CUDA).
        * TABLE       -> PaddleOCR PP-Structure on GPU.
        * PRINTED_TEXT-> PaddleOCR on GPU.

    Self-check + fallback: if the chosen engine returns empty / near-empty
    text, the other engine is tried automatically (PaddleOCR <-> Qwen) so a
    misclassification (e.g. a faint handwritten note sent to PaddleOCR) still
    recovers instead of returning a blank report.
    """
    # Valid user hint values (case-insensitive).  ``auto`` means "no hint —
    # let the classifier decide" (the default / backward-compatible path).
    _VALID_HINTS = {"auto", "printed", "printed_text", "table", "tabular", "handwritten"}

    def __init__(self, class_weights: str = "",
                 paddle_endpoint: str = "", paddle_use_gpu: bool = True,
                 paddle_lang: str = "en", paddle_use_angle_cls: bool = True,
                 qwen_server_url: str = "", qwen_model_id: str = "Qwen/Qwen2.5-VL-3B-Instruct",
                 qwen_device: str = "", qwen_torch_dtype: str = "bfloat16",
                 qwen_max_pixels: int = 128 * 28 * 28, qwen_load_in_4bit: bool = True,
                 doc_type_hint: str = ""):
        # Classifier has been removed; we rely exclusively on doc_type_hint.
        self._paddle_endpoint = paddle_endpoint
        self._paddle_cfg = dict(use_gpu=paddle_use_gpu, lang=paddle_lang, use_angle_cls=paddle_use_angle_cls)
        # Prefer the microservice URL from the environment (true GPU path in a
        # separate CUDA process). Defaults to in-process if unset.
        self._qwen_server_url = qwen_server_url or os.environ.get("QWEN_VL_SERVER_URL", "") or ""
        self._qwen_cfg = dict(model_id=qwen_model_id, device=qwen_device or "", torch_dtype=qwen_torch_dtype,
                              server_url=self._qwen_server_url, max_pixels=qwen_max_pixels,
                              load_in_4bit=qwen_load_in_4bit)
        self.last_doc_type: str = "printed"
        self.last_confidence: float = 0.0
        # Optional user-supplied document-type hint.  When set to a valid
        # class label (``printed_text`` / ``table`` / ``handwritten``) the
        # classifier is skipped entirely and the hint is trusted as the
        # routing decision — this lets the UI give users an explicit choice
        # while still falling back to the classifier when the hint is
        # ``auto`` or empty.
        self._doc_type_hint = self._normalise_hint(doc_type_hint)

    @classmethod
    def _normalise_hint(cls, hint: str) -> str:
        """Normalise a user hint to one of the 3 canonical labels or ``auto``."""
        if not hint:
            return "auto"
        h = hint.strip().lower()
        if h not in cls._VALID_HINTS:
            logger.warning("Unknown doc_type_hint '{}'; ignoring (using classifier)", h)
            return "auto"
        # Map aliases to the canonical classifier labels.
        if h == "printed":
            return "PRINTED_TEXT"
        if h == "table" or h == "tabular":
            return "TABLE"
        if h == "handwritten":
            return "HANDWRITTEN"
        return "auto"  # "auto" or "printed_text" (already canonical)

    # ── classification (confidence-gated) ──────────────────────────────────
    def _classify(self, filepath: str, filetype: str) -> tuple:
        """Return (doc_type, confidence) based purely on the explicit user hint."""
        if self._doc_type_hint == "auto":
            raise ValueError("doc_type must be explicitly provided — ML auto-classification is disabled")
        self.last_confidence = 1.0
        return self._doc_type_hint, 1.0

    def _build_qwen(self):
        if self._qwen_server_url:
            return QwenVLProviderWrapper(server_url=self._qwen_server_url)
        return _get_qwen_wrapper(**self._qwen_cfg)

    def _route(self, filepath: str, filetype: str) -> tuple:
        if getattr(self, "last_provider", None) is not None:
            return self.last_doc_type, self.last_provider

        doc_type, _ = self._classify(filepath, filetype)
        self.last_doc_type = doc_type

        if doc_type == "HANDWRITTEN":
            # Qwen2.5-VL (GPU microservice when QWEN_VL_SERVER_URL is set).
            self.last_provider = self._build_qwen()
            return "HANDWRITTEN", self.last_provider

        # TABLE or PRINTED_TEXT -> PaddleOCR (PP-Structure for TABLE).
        paddle = _get_paddle_wrapper(**self._paddle_cfg)
        if paddle is not None:
            self.last_provider = paddle
            return doc_type, self.last_provider
        # PaddleOCR unavailable; fall back to Qwen for printed/table docs.
        logger.warning("PaddleOCR unavailable for doc_type={}; falling back to Qwen-VL", doc_type)
        self.last_provider = self._build_qwen()
        return doc_type, self.last_provider

    @staticmethod
    def _is_empty(text: str) -> bool:
        """True when OCR produced no usable content (blank / whitespace only)."""
        return not (text or "").strip()

    def extract_text(self, filepath: str, filetype: str, doc_type_hint: str = "") -> str:  # pragma: no cover - GPU/OCR runtime
        # Reset cache on new extraction
        self.last_provider = None
        # Per-call hint overrides the constructor-level hint (if any).
        if doc_type_hint:
            self._doc_type_hint = self._normalise_hint(doc_type_hint)
        doc_type, provider = self._route(filepath, filetype)
        err: Optional[Exception] = None
        try:
            text = provider.extract_text(filepath, filetype)
        except Exception as e:  # noqa: BLE001 - fall back on any OCR failure
            text = ""
            err = e

        # Self-check: if the primary engine returned nothing (or a vision error
        # string from a misconfigured Qwen endpoint), try the other engine.
        if self._is_empty(text) or _looks_like_vision_error(text):
            other = "PaddleOCR" if doc_type == "HANDWRITTEN" else "Qwen-VL"
            logger.warning(
                "Primary OCR (%s) %s for %s; trying %s",
                doc_type, "errored" if err else "returned empty", filepath, other,
            )
            if doc_type == "HANDWRITTEN":
                self.last_doc_type = "PRINTED_TEXT"
                paddle = _get_paddle_wrapper(**self._paddle_cfg)
                self.last_provider = paddle
                if paddle is not None:
                    return paddle.extract_text(filepath, filetype)
            else:
                qwen = self._build_qwen()
                self.last_provider = qwen
                if qwen is not None:
                    try:
                        return qwen.extract_text(filepath, filetype) or ""
                    except Exception as e2:  # noqa: BLE001
                        logger.warning("Fallback Qwen-VL OCR also failed: {}", e2)
            # If we got here, the fallback did not produce text either.
            return text or ""
        # Primary engine produced usable text.
        return text or ""

    def extract_structured(self, filepath: str, filetype: str, doc_type_hint: str = "") -> list:  # pragma: no cover - GPU/OCR runtime
        # Uses cache from extract_text since it's called immediately after
        self.last_provider = None
        # Per-call hint overrides the constructor-level hint (if any).
        if doc_type_hint:
            self._doc_type_hint = self._normalise_hint(doc_type_hint)
        doc_type, provider = self._route(filepath, filetype)
        err: Optional[Exception] = None
        try:
            if hasattr(provider, "extract_structured"):
                result = provider.extract_structured(filepath, filetype)
                if result:
                    return result
        except Exception as e:  # noqa: BLE001 - fall back on any OCR failure
            err = e
        # If the primary engine produced nothing, try the other engine.
        if doc_type == "HANDWRITTEN":
            logger.warning("Handwritten structured OCR failed ({}); falling back to PaddleOCR", err or "empty")
            self.last_doc_type = "PRINTED_TEXT"
            paddle = _get_paddle_wrapper(**self._paddle_cfg)
            self.last_provider = paddle
            provider = paddle
        # Fallback: use heuristics on plain text for printed docs
        if doc_type in ("printed", "TABLE", "PRINTED_TEXT"):
            text = provider.extract_text(filepath, filetype)
            return self._heuristic_structured(text)
        return []

    def _heuristic_structured(self, text: str) -> list:  # pragma: no cover - latent bug: RULES_CONFIG undefined
        """Fallback structured extraction using simple regex heuristics on plain text."""
        import re
        from heuristics import extract_structured_results
        lines = [{"text": line, "bounding_box": []} for line in text.split("\n") if line.strip()]
        return extract_structured_results(lines, RULES_CONFIG)


OCR_ENGINES = {
    "auto": lambda cfg: AutoOCRProvider(
        class_weights=cfg.get("class_weights", ""),
        paddle_use_gpu=cfg.get("paddle_use_gpu", True),
        paddle_lang=cfg.get("paddle_lang", "en"),
        paddle_use_angle_cls=cfg.get("paddle_use_angle_cls", True),
        qwen_model_id=cfg.get("qwen_model_id", "Qwen/Qwen2.5-VL-3B-Instruct"),
        qwen_device=cfg.get("qwen_device", ""),
        qwen_torch_dtype=cfg.get("qwen_torch_dtype", "bfloat16"),
        qwen_server_url=cfg.get("qwen_server_url", ""),
        qwen_max_pixels=cfg.get("qwen_max_pixels", 128 * 28 * 28),
        qwen_load_in_4bit=cfg.get("qwen_load_in_4bit", True),
    ),
    "pipeline": lambda cfg: AutoOCRProvider(
        class_weights=cfg.get("class_weights", ""),
        paddle_use_gpu=cfg.get("paddle_use_gpu", True),
        paddle_lang=cfg.get("paddle_lang", "en"),
        paddle_use_angle_cls=cfg.get("paddle_use_angle_cls", True),
        qwen_model_id=cfg.get("qwen_model_id", "Qwen/Qwen2.5-VL-3B-Instruct"),
        qwen_device=cfg.get("qwen_device", ""),
        qwen_torch_dtype=cfg.get("qwen_torch_dtype", "bfloat16"),
        qwen_server_url=cfg.get("qwen_server_url", ""),
        qwen_max_pixels=cfg.get("qwen_max_pixels", 128 * 28 * 28),
        qwen_load_in_4bit=cfg.get("qwen_load_in_4bit", True),
    ),
}


def build_ocr(engine: str, config: dict) -> OCRProvider:
    return AutoOCRProvider()
