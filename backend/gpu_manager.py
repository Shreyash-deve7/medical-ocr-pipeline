"""
gpu_manager.py — centralised GPU model preloading and status reporting.

Keeps track of which heavy models (classifier CNN, PaddleOCR, Qwen-VL) have
been loaded onto the GPU, and provides a single ``preload_models()`` entry
point called at server startup so the NVIDIA GPU is warm before the first
request arrives (instead of lazy-loading on first OCR, which left the GPU
idle and the Intel iGPU doing OpenCV work).

Also exposes ``gpu_status()`` for the ``/api/gpu/status`` endpoint so the
frontend can show the user what is loaded and offer a "preload" button.
"""
from __future__ import annotations

import os
import threading
from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional

# ── Singleton state ──────────────────────────────────────────────────────────
_lock = threading.Lock()
_preload_started = False
_preload_done = False
_preload_error: Optional[str] = None

# Per-model status
_classifier_loaded = False
_classifier_error: Optional[str] = None
_paddle_loaded = False
_paddle_error: Optional[str] = None
_paddle_using_gpu = False
_qwen_loaded = False
_qwen_error: Optional[str] = None

# CUDA info
_cuda_available = False
_cuda_device_name = ""
_torch_version = ""


@dataclass
class GPUStatus:
    """Snapshot of GPU / model-load state for the status endpoint."""
    cuda_available: bool
    cuda_device_name: str
    torch_version: str
    preload_started: bool
    preload_done: bool
    preload_error: Optional[str]
    classifier_loaded: bool
    classifier_error: Optional[str]
    paddle_loaded: bool
    paddle_using_gpu: bool
    paddle_error: Optional[str]
    qwen_loaded: bool
    qwen_error: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _detect_cuda() -> None:
    """Populate ``_cuda_available`` / ``_cuda_device_name`` / ``_torch_version``."""
    global _cuda_available, _cuda_device_name, _torch_version
    try:
        import torch
        _torch_version = torch.__version__
        _cuda_available = torch.cuda.is_available()
        if _cuda_available:
            _cuda_device_name = torch.cuda.get_device_name(0)
    except ImportError:
        _cuda_available = False


def _preload_classifier() -> None:
    """Eagerly construct the DocumentClassifier so the CNN weights load on GPU."""
    global _classifier_loaded, _classifier_error
    try:
        from document_classifier import DocumentClassifier, DEFAULT_WEIGHTS_PATH
        wp = DEFAULT_WEIGHTS_PATH if os.path.exists(DEFAULT_WEIGHTS_PATH) else None
        clf = DocumentClassifier(weights_path=wp)
        # Touch the model to force it onto the device.
        if clf.model is not None:
            import numpy as np
            dummy = np.zeros((224, 224, 3), dtype=np.uint8)
            clf.predict_3class(dummy)
        _classifier_loaded = True
        print(f"[GPU preload] Classifier CNN loaded on {clf.device}"
              f" (weights={'yes' if wp else 'no'})")
    except Exception as e:
        _classifier_error = str(e)
        print(f"[GPU preload] Classifier failed: {e}")


def _preload_paddle() -> None:
    """Eagerly initialise the PaddleOCR singleton and verify GPU usage."""
    global _paddle_loaded, _paddle_error, _paddle_using_gpu
    try:
        import backend.ocr.providers.paddle_provider as pop
        pop._verify_gpu()
        pop._get_ocr(use_gpu=True)
        # Re-check after init
        _paddle_using_gpu = bool(pop._GPU_ACTIVE)
        _paddle_loaded = True
        print(f"[GPU preload] PaddleOCR loaded (GPU={_paddle_using_gpu})")
    except Exception as e:
        _paddle_error = str(e)
        print(f"[GPU preload] PaddleOCR failed: {e}")


def _preload_qwen() -> None:
    """Eagerly load the Qwen2.5-VL model onto the GPU (4-bit).

    This is the heaviest model (~3B params). Loading it at startup means the
    first handwritten OCR request is fast and the GPU is warm. If it fails
    (e.g. model not downloaded yet) we record the error but don't block
    startup — the lazy path in ``qwen_vl_provider`` will retry on demand.
    """
    global _qwen_loaded, _qwen_error
    try:
        from backend.ocr.providers.qwen_provider import QwenVLProvider, _get_model
        import torch
        dtype = torch.bfloat16
        _get_model("Qwen/Qwen2.5-VL-3B-Instruct", "cuda", dtype, load_in_4bit=True)
        _qwen_loaded = True
        print("[GPU preload] Qwen2.5-VL loaded on cuda (4-bit)")
    except Exception as e:
        _qwen_error = str(e)
        print(f"[GPU preload] Qwen2.5-VL failed (will lazy-load on first request): {e}")


def preload_models(blocking: bool = True) -> None:
    """Preload all heavy models onto the GPU.

    :param blocking: if True (default, used at startup) load synchronously.
        if False, run in a background thread (used by the API "preload" button
        so the HTTP response returns immediately).
    """
    global _preload_started, _preload_done, _preload_error
    with _lock:
        if _preload_started and not _preload_done:
            return  # already in progress
        _preload_started = True
        _preload_done = False
        _preload_error = None

    def _do_preload():
        global _preload_done, _preload_error
        try:
            _detect_cuda()
            _preload_classifier()
            _preload_paddle()
            _preload_qwen()
        except Exception as e:
            _preload_error = str(e)
        finally:
            with _lock:
                _preload_done = True

    if blocking:
        _do_preload()
    else:
        t = threading.Thread(target=_do_preload, daemon=True)
        t.start()


def gpu_status() -> GPUStatus:
    """Return a snapshot of the current GPU / model-load state."""
    _detect_cuda()
    return GPUStatus(
        cuda_available=_cuda_available,
        cuda_device_name=_cuda_device_name,
        torch_version=_torch_version,
        preload_started=_preload_started,
        preload_done=_preload_done,
        preload_error=_preload_error,
        classifier_loaded=_classifier_loaded,
        classifier_error=_classifier_error,
        paddle_loaded=_paddle_loaded,
        paddle_using_gpu=_paddle_using_gpu,
        paddle_error=_paddle_error,
        qwen_loaded=_qwen_loaded,
        qwen_error=_qwen_error,
    )
