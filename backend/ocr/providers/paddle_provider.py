"""
paddle_ocr_provider.py — PaddleOCR GPU backend for printed medical reports.

Adapted for the PaddleOCR 2.x API. Uses the native CUDA 12.9 wheel
(paddlepaddle-gpu 3.3.1) per WORKING_GPU_SETUP.md — the GPU works natively on
Windows (RTX 5060 / Blackwell sm_120), so no CPU fallback or DirectML is needed.

Provides a PaddleOCRProvider that implements the MedVault OCRProvider interface
and additionally exposes structured extraction (test name / value / reference
range) via heuristics.

Designed for PRINTED reports (clean scans / photos of printed lab sheets).
For handwritten reports, a different engine should be used.
"""
from __future__ import annotations

# NumPy 2.0 compatibility shim (before importing anything else that might import imgaug)
import numpy as np
if not hasattr(np, "sctypes"):
    np.sctypes = {
        "int": [np.int8, np.int16, np.int32, np.int64],
        "uint": [np.uint8, np.uint16, np.uint32, np.uint64],
        "float": [np.float16, np.float32, np.float64],
        "complex": [np.complex64, np.complex128],
        "others": [bool, object, bytes, str, np.void],
    }

# Shadow tools.py workaround: prepend paddleocr site-packages folder to sys.path
import sys
import os
import site
try:
    for _sp in site.getsitepackages():
        _po = os.path.join(_sp, "paddleocr")
        if os.path.isdir(os.path.join(_po, "tools")):
            if _po not in sys.path:
                sys.path.insert(0, _po)
            break
except Exception:
    pass

import ctypes
import importlib.util
import json
import logging
import threading
from pathlib import Path

import cv2
from PIL import Image

def _configure_windows_dll_search() -> None:
    """Ensure Windows can resolve Paddle's bundled CUDA/cuDNN DLLs.

    The Paddle wheel ships its native libraries in site-packages/paddle/libs.
    We set the default DLL search path before importing paddle and explicitly
    add the package's libs directory when it exists.
    """
    try:
        ctypes.windll.kernel32.SetDefaultDllDirectories(0x00001500)  # LOAD_LIBRARY_SEARCH_DEFAULT_DIRS
    except Exception:
        pass

    try:
        spec = importlib.util.find_spec("paddle")
    except Exception:
        return
    if not spec or not spec.origin:
        return
    paddle_dir = Path(spec.origin).resolve().parent
    for candidate in (paddle_dir, paddle_dir / "libs"):
        try:
            if candidate.exists():
                os.add_dll_directory(str(candidate))
        except Exception:
            pass


# Windows: let the system resolve CUDA/cuDNN DLLs from the Paddle wheel's own
# directories instead of a stale System32 copy. Must run BEFORE importing paddle.
_configure_windows_dll_search()

from heuristics import extract_structured_results
from image_processing import preprocess_image

logger = logging.getLogger("paddle_ocr_provider")


# ── HTML table parsing (PP-Structure output) ─────────────────────────────────
def html_to_table(html: str) -> list:
    """
    Parse a PP-Structure table ``<table>`` HTML fragment into a 2D
    ``list[list[str]]`` (rows of cell strings), using beautifulsoup4 + lxml.

    Returns an empty list if no table is found or parsing fails.
    """
    try:
        from bs4 import BeautifulSoup
    except Exception as e:
        logger.warning("beautifulsoup4 not available for table parsing: %s", e)
        return []
    try:
        soup = BeautifulSoup(html or "", "lxml")
        tables = soup.find_all("table")
        if not tables:
            return []
        result = []
        for tr in tables[0].find_all("tr"):
            row = [cell.get_text(strip=True) for cell in tr.find_all(["td", "th"])]
            result.append(row)
        return result
    except Exception as e:
        logger.warning("Failed to parse PP-Structure HTML table: %s", e)
        return []

# PaddlePaddle GPU mode is preferred on the documented Windows setup.
# CPU remains available if the user explicitly opts out or the GPU wheel is
# unavailable, but the default path now follows the native CUDA 12.9 flow.
_DEFAULT_USE_GPU = True
_DEFAULT_LANG = os.environ.get("PADDLE_LANG", "en")
_DEFAULT_MAX_DIM = int(os.environ.get("PADDLE_TARGET_MAX_DIM", "1600"))
_DEFAULT_PDF_DPI = int(os.environ.get("PADDLE_PDF_DPI", "200"))
_DEFAULT_MIN_CONF = float(os.environ.get("PADDLE_MIN_CONF", "0.0"))

# ── Load medical rules once (used for structured extraction) ──────────────────
_RULES_PATH = Path(__file__).parent / "medical_rules.json"
try:
    with open(_RULES_PATH, "r", encoding="utf-8") as _f:
        RULES_CONFIG = json.load(_f)
except Exception:
    RULES_CONFIG = {}

# ── Lazy singleton PaddleOCR instances (thread-safe, per config) ───────────────
_OCR_INSTANCES: dict = {}
_OCR_LOCK = threading.Lock()
_GPU_ACTIVE: bool | None = None
_GPU_VERIFIED = False

# ── Lazy singleton PaddleOCR PP-Structure table engine ────────────────────────
_PP_STRUCTURE: object | None = None
_PP_STRUCTURE_LOCK = threading.Lock()


def _verify_gpu() -> bool:
    """Log PaddlePaddle CUDA status once. Returns True if a GPU device is active."""
    global _GPU_ACTIVE, _GPU_VERIFIED
    if _GPU_VERIFIED:
        return bool(_GPU_ACTIVE)
    _GPU_VERIFIED = True
    try:
        import paddle
        ver = paddle.__version__
        compiled = paddle.is_compiled_with_cuda()
        device = paddle.device.get_device()
        _GPU_ACTIVE = "gpu" in device
        logger.info("PaddlePaddle %s | compiled_with_cuda=%s | device=%s",
                    ver, compiled, device)
        if not _GPU_ACTIVE:
            logger.warning(
                "PaddleOCR is NOT using the GPU (%s). Verify the paddlepaddle-gpu "
                "3.3.1 (cu129) wheel is installed (see WORKING_GPU_SETUP.md).",
                device,
            )
    except Exception as e:
        _GPU_ACTIVE = False
        logger.warning("Could not verify Paddle GPU status: %s", e)
    return bool(_GPU_ACTIVE)


def _get_ocr(use_gpu: bool = _DEFAULT_USE_GPU, lang: str = _DEFAULT_LANG,
             use_angle_cls: bool = True):
    """Return a shared PaddleOCR instance, initialising it on first use.
    Separate instances are cached per (use_gpu, lang, use_angle_cls) config.
    GPU is used natively when available (WORKING_GPU_SETUP.md)."""
    key = (bool(use_gpu), lang, use_angle_cls)
    if key not in _OCR_INSTANCES:
        with _OCR_LOCK:
            if key not in _OCR_INSTANCES:
                _verify_gpu()
                # Auto-disable GPU if verification failed or unavailable
                if not _GPU_ACTIVE and use_gpu:
                    logger.warning("Paddle GPU not available; falling back to CPU")
                    use_gpu = False
                    key = (False, lang, use_angle_cls)
                old_cuda = os.environ.pop("CUDA_VISIBLE_DEVICES", None)
                if not use_gpu:
                    os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
                try:
                    from paddleocr import PaddleOCR
                finally:
                    if old_cuda is not None:
                        os.environ["CUDA_VISIBLE_DEVICES"] = old_cuda
                    elif "CUDA_VISIBLE_DEVICES" in os.environ and os.environ["CUDA_VISIBLE_DEVICES"] == "-1":
                        del os.environ["CUDA_VISIBLE_DEVICES"]
                logger.info("Initializing PaddleOCR (use_gpu=%s, lang=%s, cls=%s)...",
                            use_gpu, lang, use_angle_cls)
                _OCR_INSTANCES[key] = PaddleOCR(
                    use_gpu=bool(use_gpu),
                    lang=lang,
                    use_angle_cls=use_angle_cls,
                    show_log=False,
                )
                logger.info("PaddleOCR initialized.")
    return _OCR_INSTANCES[key]


def _ocr_to_lines(result) -> list[dict]:
    """Convert PaddleOCR 2.x result to standard lines format."""
    lines = []
    if result is None:
        return lines
    for page in result:
        if page is None:
            continue
        for line in page:
            if line is None or len(line) != 2:
                continue
            bbox, (text, conf) = line
            lines.append({
                "text": text,
                "confidence": round(float(conf), 4),
                "bbox": bbox,
            })
    return lines


def _sort_reading_order(lines: list[dict]) -> list[dict]:
    """Sort OCR lines top-to-bottom, then left-to-right, to follow document order.
    PaddleOCR returns lines in detection order, which can scatter across columns."""
    def _key(l: dict):
        bbox = l.get("bbox") or [[0, 0]]
        ys = [p[1] for p in bbox]
        xs = [p[0] for p in bbox]
        return (min(ys), min(xs))
    return sorted(lines, key=_key)


def _ocr_array(img_bgr: np.ndarray, use_gpu: bool, lang: str,
               use_angle_cls: bool, min_conf: float) -> list[dict]:
    ocr = _get_ocr(use_gpu=use_gpu, lang=lang, use_angle_cls=use_angle_cls)
    result = ocr.ocr(img_bgr, cls=True)
    lines = _ocr_to_lines(result)
    if min_conf and min_conf > 0:
        lines = [l for l in lines if l["confidence"] >= min_conf]
    return lines


def run_paddle_ocr(path: str, use_gpu: bool = _DEFAULT_USE_GPU, lang: str = _DEFAULT_LANG,
                   use_angle_cls: bool = True, target_max_dim: int = _DEFAULT_MAX_DIM,
                   min_conf: float = _DEFAULT_MIN_CONF) -> list[dict]:
    """
    Run PaddleOCR on a single image file and return a list of region dicts:
        {"text": str, "confidence": float, "bbox": [[x,y], ...]}
    Lines are returned in reading order, optionally filtered by min confidence.
    """
    img_bgr = preprocess_image(path, target_max_dim=target_max_dim)
    lines = _ocr_array(img_bgr, use_gpu, lang, use_angle_cls, min_conf)
    return _sort_reading_order(lines)


def _rasterize_pdf_pages(pdf_path: str, dpi: int = _DEFAULT_PDF_DPI,
                         target_max_dim: int = _DEFAULT_MAX_DIM) -> list[np.ndarray]:
    """Render each PDF page straight to a preprocessed BGR ndarray (no temp files)."""
    import fitz  # PyMuPDF
    pages: list[np.ndarray] = []
    doc = fitz.open(pdf_path)
    try:
        for page in doc:
            pix = page.get_pixmap(dpi=dpi)
            arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
                pix.height, pix.width, pix.n if pix.n in (1, 3, 4) else 1
            )
            if pix.n == 4:
                arr = cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR)
            elif pix.n == 1:
                arr = cv2.cvtColor(arr, cv2.COLOR_GRAY2BGR)
            else:
                arr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
            pages.append(preprocess_image(arr, target_max_dim=target_max_dim))
    finally:
        doc.close()
    return pages


def run_paddle_ocr_on_document(path: str, use_gpu: bool = _DEFAULT_USE_GPU,
                               lang: str = _DEFAULT_LANG, use_angle_cls: bool = True,
                               target_max_dim: int = _DEFAULT_MAX_DIM,
                               min_conf: float = _DEFAULT_MIN_CONF,
                               pdf_dpi: int = _DEFAULT_PDF_DPI) -> list[dict]:
    """
    Run PaddleOCR on an image or a PDF (PDF pages are rasterised first).
    Returns the combined, reading-ordered list of region dicts across all pages.
    """
    ext = Path(path).suffix.lower()
    if ext == ".pdf":
        pages = _rasterize_pdf_pages(path, dpi=pdf_dpi, target_max_dim=target_max_dim)
        all_lines: list[dict] = []
        for img in pages:
            all_lines.extend(_ocr_array(img, use_gpu, lang, use_angle_cls, min_conf))
        return _sort_reading_order(all_lines)
    return run_paddle_ocr(path, use_gpu=use_gpu, lang=lang, use_angle_cls=use_angle_cls,
                          target_max_dim=target_max_dim, min_conf=min_conf)


def summarize_lines(lines: list[dict]) -> dict:
    """Compute lightweight aggregate stats for an OCR result list."""
    confs = [l["confidence"] for l in lines if "confidence" in l]
    return {
        "line_count": len(lines),
        "avg_confidence": round(float(sum(confs) / len(confs)), 4) if confs else 0.0,
        "use_gpu": bool(_GPU_ACTIVE) if _GPU_ACTIVE is not None else False,
    }


def warmup(use_gpu: bool = _DEFAULT_USE_GPU, lang: str = _DEFAULT_LANG,
            use_angle_cls: bool = True) -> None:
    """Eagerly verify the GPU and load the PaddleOCR model so the first request
    does not pay model-load latency."""
    _verify_gpu()
    _get_ocr(use_gpu=use_gpu, lang=lang, use_angle_cls=use_angle_cls)


def _load_image_for_structure(path: str, filetype: str,
                              target_max_dim: int = _DEFAULT_MAX_DIM) -> np.ndarray | None:
    """Load an image (or first PDF page) as a preprocessed BGR ndarray for PP-Structure."""
    ext = Path(path).suffix.lower()
    if ext == ".pdf":
        pages = _rasterize_pdf_pages(path, target_max_dim=target_max_dim)
        return pages[0] if pages else None
    try:
        return preprocess_image(path, target_max_dim=target_max_dim)
    except Exception as e:
        logger.warning("Could not load image %s for PP-Structure: %s", path, e)
        return None


def warmup_pp_structure(lang: str = _DEFAULT_LANG) -> None:
    """Eagerly load the PP-Structure model so the first TABLE request is fast."""
    global _PP_STRUCTURE
    if _PP_STRUCTURE is None:
        with _PP_STRUCTURE_LOCK:
            if _PP_STRUCTURE is None:
                try:
                    from paddleocr import PPStructure
                except Exception as e:
                    logger.warning("PP-Structure warmup skipped (import error): %s", e)
                    return
                logger.info("Initializing PaddleOCR PP-Structure (lang=%s)...", lang)
                _PP_STRUCTURE = PPStructure(show_log=False, lang=lang)
                logger.info("PP-Structure initialized.")


class PaddleOCRProvider:
    """
    MedVault OCRProvider backed by PaddleOCR (GPU) for printed reports.

    Config keys (all optional):
        use_gpu        (bool, default True — native CUDA per WORKING_GPU_SETUP.md)
        lang           (str,  default "en")
        use_angle_cls  (bool, default True)
        target_max_dim (int,  default 1600 — longest preprocessed edge)
        min_conf       (float,default 0.0 — drop lines below this confidence)
    """

    def __init__(self, use_gpu: bool = _DEFAULT_USE_GPU, lang: str = _DEFAULT_LANG,
                 use_angle_cls: bool = True, target_max_dim: int = _DEFAULT_MAX_DIM,
                 min_conf: float = _DEFAULT_MIN_CONF):
        self.use_gpu = use_gpu
        self.lang = lang
        self.use_angle_cls = use_angle_cls
        self.target_max_dim = target_max_dim
        self.min_conf = min_conf

    def extract_text(self, filepath: str, filetype: str) -> str:
        """Return the full OCR text for a printed report (image or PDF)."""
        lines = run_paddle_ocr_on_document(
            filepath, use_gpu=self.use_gpu, lang=self.lang,
            use_angle_cls=self.use_angle_cls, target_max_dim=self.target_max_dim,
            min_conf=self.min_conf,
        )
        return "\n".join(l["text"] for l in lines).strip()

    def extract_structured(self, filepath: str, filetype: str) -> list[dict]:
        """
        Run OCR and return structured test results (name / value / reference range)
        using the medical heuristics module. Input is reading-ordered.
        """
        lines = run_paddle_ocr_on_document(
            filepath, use_gpu=self.use_gpu, lang=self.lang,
            use_angle_cls=self.use_angle_cls, target_max_dim=self.target_max_dim,
            min_conf=self.min_conf,
        )
        formatted = [{"text": l["text"], "bounding_box": l["bbox"]} for l in lines]
        return extract_structured_results(formatted, RULES_CONFIG)

    def extract_table_pp_structure(self, filepath: str, filetype: str) -> list:
        """
        Run PaddleOCR PP-Structure on a TABLE document (image or PDF) and return
        the recovered table as a 2D ``list[list[str]]`` (rows of cell strings).

        Returns an empty list if no table region is found or if PP-Structure is
        unavailable (model not downloaded / import error) — the caller is
        expected to fall back to basic OCR row grouping.
        """
        rows: list = []
        try:
            from paddleocr import PPStructure
        except Exception as e:
            logger.warning("PP-Structure unavailable (import error): %s", e)
            return rows

        global _PP_STRUCTURE
        if _PP_STRUCTURE is None:
            with _PP_STRUCTURE_LOCK:
                if _PP_STRUCTURE is None:
                    logger.info("Initializing PaddleOCR PP-Structure (lang=%s)...", self.lang)
                    _PP_STRUCTURE = PPStructure(show_log=False, lang=self.lang)
                    logger.info("PP-Structure initialized.")

        # Load the (preprocessed) image as a BGR ndarray.
        img = _load_image_for_structure(filepath, filetype,
                                         target_max_dim=self.target_max_dim)
        if img is None:
            return rows

        try:
            regions = _PP_STRUCTURE(img)
        except Exception as e:
            logger.warning("PP-Structure inference failed: %s", e)
            return rows

        for region in regions or []:
            if not isinstance(region, dict):
                continue
            if region.get("type") != "table":
                continue
            res = region.get("res") or {}
            html = res.get("html")
            if not html:
                continue
            table = html_to_table(html)
            if table:
                rows = table
                break
        return rows

    def table_confidence(self, rows: list) -> float:
        """
        Best-effort confidence for a PP-Structure table.

        PP-Structure does not always surface a single global score; we use the
        region ``score`` when present, otherwise the fraction of non-empty cells
        (a fully recovered table has no blank cells).
        """
        if not rows:
            return 0.0
        total = 0
        non_empty = 0
        for r in rows:
            for cell in r:
                total += 1
                if str(cell).strip():
                    non_empty += 1
        return round(non_empty / total, 4) if total else 0.0
