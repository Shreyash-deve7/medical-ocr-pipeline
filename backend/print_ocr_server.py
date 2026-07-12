"""
print_ocr_server.py — PaddleOCR printed-OCR microservice (pipeline_v1)
===========================================================================
The pipeline_v1 `auto` OCR router (AutoOCRProvider) sends printed documents to
PRINTED_OCR_URL, default http://127.0.0.1:8001/ocr, as a multipart file upload
and expects back {"text": <extracted text>, ...}.

This server fills that gap. It runs PaddleOCR on the **GPU** using the native
CUDA 12.9 wheel (WORKING_GPU_SETUP.md) — no CPU fallback needed. Paddle (printed)
and Qwen2.5-VL (handwritten, :8002) run in SEPARATE processes (Hard Rule #2), so
enabling GPU here does not conflict with the handwritten backend.

Run:
    ..\\venv\\Scripts\\python.exe print_ocr_server.py
    (listens on http://127.0.0.1:8001)
"""
import logging
import os
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse

from paddle_ocr_provider import (
    run_paddle_ocr_on_document,
    summarize_lines,
    warmup,
    _verify_gpu,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("print_ocr_server")

app = FastAPI(title="PaddleOCR Printed OCR microservice (GPU)")

USE_GPU = os.environ.get("PADDLE_USE_GPU", "1") != "0"
LANG = os.environ.get("PADDLE_LANG", "en")
TARGET_MAX_DIM = int(os.environ.get("PADDLE_TARGET_MAX_DIM", "1600"))
MIN_CONF = float(os.environ.get("PADDLE_MIN_CONF", "0.0"))
MAX_UPLOAD_BYTES = int(os.environ.get("PADDLE_MAX_UPLOAD_BYTES", str(20 * 1024 * 1024)))


@app.on_event("startup")
def _startup():
    logger.info("Warming up PaddleOCR (use_gpu=%s, lang=%s)...", USE_GPU, LANG)
    try:
        warmup(use_gpu=USE_GPU, lang=LANG)
    except Exception:
        logger.exception("PaddleOCR warm-up failed")


@app.post("/ocr")
async def ocr(file: UploadFile = File(...)):
    try:
        data = await file.read()
        if not data:
            return JSONResponse(status_code=400, content={"error": "Empty upload."})
        if len(data) > MAX_UPLOAD_BYTES:
            return JSONResponse(status_code=413, content={"error": "Upload too large."})

        suffix = Path(file.filename or "img.png").suffix or ".png"
        tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        tmp.write(data)
        tmp.close()
        try:
            lines = run_paddle_ocr_on_document(
                tmp.name, use_gpu=USE_GPU, lang=LANG,
                target_max_dim=TARGET_MAX_DIM, min_conf=MIN_CONF,
            )
        finally:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass

        summary = summarize_lines(lines)
        text = "\n".join(l["text"] for l in lines).strip()
        return {
            "text": text,
            "lines": lines,
            "line_count": summary["line_count"],
            "avg_confidence": summary["avg_confidence"],
            "use_gpu": summary["use_gpu"],
        }
    except Exception as e:
        logger.exception("OCR failed: %s", e)
        return JSONResponse(status_code=500, content={"error": type(e).__name__, "detail": str(e)})


@app.get("/health")
def health():
    return {"status": "ok", "use_gpu": USE_GPU, "lang": LANG}


@app.get("/gpu")
def gpu():
    return {"use_gpu": _verify_gpu()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8001)
