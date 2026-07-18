"""
backend.ocr.providers — OCR engine provider implementations.

Each module in this package wraps a specific OCR backend:

  * ``paddle_provider``  — PaddleOCR (printed / table OCR, GPU)
  * ``qwen_provider``    — Qwen2.5-VL (handwritten OCR, GPU)
  * ``surya_provider``   — Surya (table / handwritten fallback)

This ``__init__.py`` makes ``backend.ocr.providers`` a regular importable
package so that ``from backend.ocr.providers.paddle_provider import ...``
resolves reliably (it was previously relying on implicit namespace-package
resolution, which is fragile and caused silent ImportError failures in
``gpu_manager.preload_models`` and ``services.ocr_service``).
"""
