"""
backend.ocr — Modular OCR routing layer.

Exports:
    run_ocr — unified OCR dispatcher (routes by doc_class to the right engine)
"""
from .router import run_ocr

__all__ = ["run_ocr"]