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
        from paddle_ocr_provider import PaddleOCRProvider
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
        from qwen_vl_provider import QwenVLProvider
        self._provider = QwenVLProvider(
            model_id=model_id,
            device=device or None,
            torch_dtype=torch_dtype,
            server_url=server_url,
            max_pixels=max_pixels,
            load_in_4bit=load_in_4bit,
        )
    def extract_text(self, filepath: str, filetype: str) -> str:  # pragma: no cover - GPU/OCR runtime
        return self._provider.extract_text(filepath, filetype)

    def extract_structured(self, filepath: str, filetype: str) -> list[dict]:  # pragma: no cover - GPU/OCR runtime
        return self._provider.extract_structured(filepath, filetype)


def _first_page_cv2(filepath: str, filetype: str) -> "np.ndarray":
    """Return the first page/image of a document as a BGR ndarray (for classification).
    Applies preprocessing (crop, enhance, normalize) for better classification accuracy."""
    from image_processing import preprocess_image
    return preprocess_image(filepath)


# Module-level singletons for caching
_classifier_cache = None
_classifier_lock = threading.Lock()
_paddle_wrapper_cache = None
_paddle_wrapper_lock = threading.Lock()
_qwen_wrapper_cache = None
_qwen_wrapper_lock = threading.Lock()


def _get_classifier(weights_path: str = ""):
    """Get cached DocumentClassifier instance."""
    global _classifier_cache
    if _classifier_cache is None:
        with _classifier_lock:
            if _classifier_cache is None:
                from document_classifier import DocumentClassifier, DEFAULT_WEIGHTS_PATH
                # Auto-discover the trained weights when no explicit path is given.
                wp = weights_path or DEFAULT_WEIGHTS_PATH
                _classifier_cache = DocumentClassifier(weights_path=wp or None)
    return _classifier_cache


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
                        model_id=model_id, device=device or "", torch_dtype=torch_dtype,
                        max_pixels=max_pixels, load_in_4bit=load_in_4bit))
    return _qwen_wrapper_cache[1]


class AutoOCRProvider(OCRProvider):
    """
    MedVault OCRProvider that auto-detects whether a document is 'printed' or
    'handwritten' and routes it to the right backend.

    Default: in-process GPU models (microservices optional via env vars)
        printed     -> PaddleOCR in-process (GPU)  -- set PADDLE_ENDPOINT to use microservice
        handwritten -> Qwen2.5-VL in-process (4-bit GPU) -- set QWEN_VL_SERVER_URL to use microservice
    """
    def __init__(self, class_weights: str = "",
                 paddle_endpoint: str = "", paddle_use_gpu: bool = True,
                 paddle_lang: str = "en", paddle_use_angle_cls: bool = True,
                 qwen_server_url: str = "", qwen_model_id: str = "Qwen/Qwen2.5-VL-3B-Instruct",
                 qwen_device: str = "", qwen_torch_dtype: str = "bfloat16",
                 qwen_max_pixels: int = 128 * 28 * 28, qwen_load_in_4bit: bool = True):
        self._classifier = _get_classifier(class_weights)
        self._paddle_endpoint = paddle_endpoint
        self._paddle_cfg = dict(use_gpu=paddle_use_gpu, lang=paddle_lang, use_angle_cls=paddle_use_angle_cls)
        self._qwen_server_url = qwen_server_url or ""
        self._qwen_cfg = dict(model_id=qwen_model_id, device=qwen_device or "", torch_dtype=qwen_torch_dtype,
                              server_url=self._qwen_server_url, max_pixels=qwen_max_pixels,
                              load_in_4bit=qwen_load_in_4bit)
        self.last_doc_type: str = "printed"

    def _route(self, filepath: str, filetype: str) -> tuple:
        if hasattr(self, "last_doc_type") and hasattr(self, "last_provider") and self.last_provider is not None:
            return self.last_doc_type, self.last_provider

        img = _first_page_cv2(filepath, filetype)
        doc_type = self._classifier.predict_3class(img).doc_class
        self.last_doc_type = doc_type

        if doc_type == "HANDWRITTEN":
            if self._qwen_server_url:
                self.last_provider = QwenVLProviderWrapper(server_url=self._qwen_server_url)
            else:
                self.last_provider = _get_qwen_wrapper(**self._qwen_cfg)
            return "HANDWRITTEN", self.last_provider

        # TABLE or PRINTED_TEXT -> PaddleOCR (PP-Structure for TABLE added in Session 3)
        paddle = _get_paddle_wrapper(**self._paddle_cfg)
        if paddle is not None:
            self.last_provider = paddle
            return doc_type, self.last_provider
        # PaddleOCR unavailable; fall back to Qwen for printed/table docs.
        logger.warning("PaddleOCR unavailable for doc_type={}; falling back to Qwen-VL", doc_type)
        if self._qwen_server_url:
            self.last_provider = QwenVLProviderWrapper(server_url=self._qwen_server_url)
        else:
            self.last_provider = _get_qwen_wrapper(**self._qwen_cfg)
        return doc_type, self.last_provider

    def extract_text(self, filepath: str, filetype: str) -> str:  # pragma: no cover - GPU/OCR runtime
        # Reset cache on new extraction
        self.last_provider = None
        doc_type, provider = self._route(filepath, filetype)
        err: Optional[Exception] = None
        try:
            text = provider.extract_text(filepath, filetype)
        except Exception as e:  # noqa: BLE001 - fall back on any OCR failure
            text = ""
            err = e
        # Vision model (Qwen-VL) misconfigured / text-only / no GPU, OR it returned
        # an error string instead of transcription: fall back to PaddleOCR so a
        # (likely printed) report still OCRs instead of crashing.
        if doc_type in ("HANDWRITTEN", "handwritten") and (err is not None or _looks_like_vision_error(text)):
            if err is not None:
                logger.warning("Handwritten OCR failed ({}); falling back to PaddleOCR", err)
            else:
                logger.warning("Handwritten OCR returned a vision error; falling back to PaddleOCR")
            self.last_doc_type = "PRINTED_TEXT"
            paddle = _get_paddle_wrapper(**self._paddle_cfg)
            self.last_provider = paddle
            if paddle is not None:
                return paddle.extract_text(filepath, filetype)
            raise err or RuntimeError("Handwritten OCR failed and PaddleOCR fallback unavailable")
        if err is not None:
            raise err
        return text
    def _fallback_to_qwen(self, filepath: str, filetype: str, doc_type: str) -> str:
        """Fallback OCR using Qwen-VL when PaddleOCR fails for printed/table docs."""
        logger.warning("Falling back to Qwen-VL for doc_type={}", doc_type)
        qwen = _get_qwen_wrapper(
            server_url=self._qwen_server_url,
            model_id=self._qwen_cfg.get("model_id", "Qwen/Qwen2.5-VL-3B-Instruct"),
            device=self._qwen_cfg.get("device", ""),
            torch_dtype=self._qwen_cfg.get("torch_dtype", "bfloat16"),
            max_pixels=self._qwen_cfg.get("max_pixels", 128 * 28 * 28),
            load_in_4bit=self._qwen_cfg.get("load_in_4bit", True),
        )
        self.last_doc_type = doc_type
        self.last_provider = qwen
        return qwen.extract_text(filepath, filetype)

    def extract_structured(self, filepath: str, filetype: str) -> list:  # pragma: no cover - GPU/OCR runtime
        # Uses cache from extract_text since it's called immediately after
        doc_type, provider = self._route(filepath, filetype)
        err: Optional[Exception] = None
        try:
            if hasattr(provider, "extract_structured"):
                return provider.extract_structured(filepath, filetype)
        except Exception as e:  # noqa: BLE001 - fall back on any OCR failure
            err = e
        if doc_type in ("HANDWRITTEN", "handwritten") and (err is not None or _looks_like_vision_error(getattr(provider, "last_text", ""))):
            logger.warning("Handwritten structured OCR failed ({}); falling back to PaddleOCR", err or "vision error")
            doc_type = "PRINTED_TEXT"
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
