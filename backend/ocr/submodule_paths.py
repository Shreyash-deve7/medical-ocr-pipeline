"""
submodule_paths.py — Inject extern/ submodules into sys.path.

This file is imported by ocr1_table.py, ocr2_handwritten.py, and ocr3_printed.py
BEFORE any submodule-specific imports, ensuring that extern/* packages are
discoverable even when the submodules haven't been cloned.
"""
import sys
from pathlib import Path

EXTERN = Path(__file__).parent.parent.parent / "extern"

SUBMODULE_PATHS = [
    EXTERN / "ocr_table_paddle",
    EXTERN / "ocr_table_surya",
    EXTERN / "ocr_table_docling",
    EXTERN / "ocr_handwritten_trocr",
    EXTERN / "ocr_handwritten_surya",
    EXTERN / "ocr_printed_tesseract",
    EXTERN / "ocr_printed_easyocr",
    EXTERN / "ocr_printed_olmocr",
    EXTERN / "preprocessing",
]

for p in SUBMODULE_PATHS:
    if p.exists():
        sys.path.insert(0, str(p))