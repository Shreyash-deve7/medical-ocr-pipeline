"""backend/routes/reports_routes.py — report upload / file serving / OCR / analysis (Session 6).

Extracted verbatim from ``main.py``:
  POST /api/patient/upload
  GET  /api/patient/reports
  GET  /api/file/{report_id}
  POST /api/doctor/analyze
  POST /api/doctor/ocr-structured
"""
from __future__ import annotations

import json
import threading
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from auth import decode_token
from database import _get_provider_row, _migrate_reports_schema, get_db
from schemas import AnalyzeReq, StructuredOCRReq
from services.ai_service import MEDICAL_PROMPT, _extract_images, build_ai
from services.ocr_service import AutoOCRProvider

router = APIRouter()

# Ensure uploads directory exists at module load
UPLOAD_DIR = Path(__file__).resolve().parent.parent / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".webp"}


@router.post("/api/patient/upload")
async def upload_report(token: str = Form(...), file: UploadFile = File(...), bg: BackgroundTasks = None):
    """
    Upload a medical report file (PDF or image) for a patient.
    
    Args:
        token: JWT token for patient authentication (form field)
        file: Uploaded file (multipart/form-data)
        bg: Background tasks for async OCR processing
    
    Returns:
        {"report_id": "<uuid>", "filename": "<original-filename>"}
    
    Raises:
        HTTPException: 400 for invalid file, 401 for invalid token, 500 for server errors
    """
    try:
        # Decode and validate token
        payload = decode_token(token)
        patient_id = payload["sub"]
        
        # Validate file extension
        ext = Path(file.filename or "file").suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(400, f"Only PDF and image files accepted. Got: {ext or 'no extension'}")
        
        # Read and validate file content
        content = await file.read()
        if len(content) == 0:
            raise HTTPException(400, "Empty file")
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(400, f"File too large. Max size: {MAX_FILE_SIZE // (1024*1024)}MB")
        
        # Generate unique filename and save
        rid = str(uuid.uuid4())
        dest = UPLOAD_DIR / f"{rid}{ext}"
        dest.write_bytes(content)
        
        # Determine file type
        filetype = "pdf" if ext == ".pdf" else "image"
        now = datetime.now(timezone.utc).isoformat()
        
        # Save to database
        conn = get_db()
        try:
            conn.execute(
                "INSERT INTO reports (id, patient_id, filename, filepath, filetype, shared_at) VALUES (?,?,?,?,?,?)",
                (rid, patient_id, file.filename, str(dest), filetype, now),
            )
            conn.commit()
        except Exception as db_error:
            # Clean up uploaded file on DB error
            try:
                dest.unlink(missing_ok=True)
            except Exception:
                pass
            raise HTTPException(500, f"Database error: {str(db_error)}")
        finally:
            conn.close()
        
        # Kick off automatic OCR in a daemon thread (printed→PaddleOCR,
        # handwritten→Qwen-VL).  We deliberately use a bare thread instead of
        # FastAPI's BackgroundTasks so the heavy synchronous OCR work does not
        # block the ASGI worker thread (which starves subsequent requests and
        # causes "Failed to fetch" in the frontend).
        from services.pipeline_service import process_report_automatic
        threading.Thread(target=process_report_automatic, args=(rid,), daemon=True).start()
        
        return {"report_id": rid, "filename": file.filename}
    
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        # Log full traceback for debugging
        traceback.print_exc()
        raise HTTPException(500, f"Upload failed: {str(e)}")


@router.get("/api/patient/reports")
def patient_reports(token: str):
    payload = decode_token(token)
    conn = get_db()
    rows = conn.execute(
        "SELECT id, filename, filetype, shared_at, analyzed FROM reports WHERE patient_id=? ORDER BY shared_at DESC",
        (payload["sub"],),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.get("/api/file/{report_id}")
def serve_file(report_id: str):
    conn = get_db()
    row = conn.execute("SELECT filepath, filename FROM reports WHERE id=?", (report_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "File not found")
    return FileResponse(row["filepath"], filename=row["filename"])


@router.post("/api/doctor/analyze")
def analyze_report(req: AnalyzeReq):
    conn = get_db()
    _migrate_reports_schema(conn)  # ensure status/analyzed/etc. columns exist
    row = conn.execute("SELECT * FROM reports WHERE id=?", (req.report_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Report not found")
    filepath = row["filepath"]
    filetype = row["filetype"]

    ocr = AutoOCRProvider()

    ai_row = _get_provider_row(conn, req.ai_provider_id, "ai")
    if ai_row:
        ai_config = json.loads(ai_row["config"]) if isinstance(ai_row["config"], str) else ai_row["config"]
        ai = build_ai(ai_row["engine"], ai_config)
    elif req.api_key:
        from services.ai_service import GeminiProvider
        ai = GeminiProvider(api_key=req.api_key)
    else:
        conn.close()
        raise HTTPException(400, "No AI provider configured. Add one in Settings or pass an api_key.")

    try:
        ocr_text = ocr.extract_text(filepath, filetype)
        doc_type = getattr(ocr, "last_doc_type", "printed")
        structured = ocr.extract_structured(filepath, filetype) if hasattr(ocr, "extract_structured") else []
        ocr_engine = type(ocr).__name__
        images = _extract_images(filepath, filetype)
        analysis = ai.analyze(MEDICAL_PROMPT, ocr_text, images)
        conn.execute(
            "UPDATE reports SET ocr_text=?, structured_results=?, doc_type=?, ocr_engine=?, analysis=?, analyzed=1 WHERE id=?",
            (ocr_text, json.dumps(structured, ensure_ascii=False), doc_type, ocr_engine, analysis, req.report_id),
        )
        conn.commit()
    except Exception as e:
        try:
            conn.execute(
                "UPDATE reports SET status='failed', error=? WHERE id=?",
                (str(e), req.report_id),
            )
            conn.commit()
        except Exception:
            pass
        raise
    finally:
        conn.close()

    return {
        "analysis": analysis,
        "ocr_text": ocr_text,
        "doc_type": doc_type,
        "structured_results": structured,
        "ocr_engine": ocr_engine,
        "report_id": req.report_id,
        "status": "analyzed",
    }


@router.post("/api/doctor/ocr-structured")
def ocr_structured_report(req: StructuredOCRReq):
    conn = get_db()
    row = conn.execute("SELECT * FROM reports WHERE id=?", (req.report_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Report not found")
    filepath = row["filepath"]
    filetype = row["filetype"]

    ocr = AutoOCRProvider()

    try:
        ocr_text = ocr.extract_text(filepath, filetype)
        doc_type = getattr(ocr, "last_doc_type", "printed")
        structured = ocr.extract_structured(filepath, filetype) if hasattr(ocr, "extract_structured") else []
        conn.close()
        return {"ocr_text": ocr_text, "structured_results": structured, "doc_type": doc_type, "ocr_engine": type(ocr).__name__}
    except HTTPException:
        conn.close()
        raise
    except Exception as e:
        conn.close()
        raise HTTPException(500, f"Structured OCR failed: {e}")


# ── No-auth test endpoints (test-only version, no login required) ──────────
# These mirror /api/patient/upload and /api/patient/reports but operate on a
# single seeded default patient (see _seed_default_patient in main.py). They
# exist so the Patient Portal UI can upload + list reports without any token.


def _default_patient_id() -> str:
    """Return the seeded default patient id, raising a clear error if missing.

    Resolves the ``DEFAULT_PATIENT_ID`` module global from whichever ``main``
    module object actually ran the lifespan hook. When uvicorn loads
    ``backend.main:app`` the module is registered as ``backend.main``; when the
    test suite inserts ``backend/`` on ``sys.path`` and imports ``main`` it is
    registered as ``main``. Check both so the seeded id is always found.
    """
    import sys
    for modname in ("backend.main", "main"):
        mod = sys.modules.get(modname)
        if mod is not None and getattr(mod, "DEFAULT_PATIENT_ID", None):
            return mod.DEFAULT_PATIENT_ID
    raise HTTPException(500, "Default patient not seeded yet")



@router.post("/api/test/upload")
async def test_upload_report(file: UploadFile = File(...), bg: BackgroundTasks = None):
    """Upload a report for the default patient — no auth token required."""
    try:
        patient_id = _default_patient_id()

        ext = Path(file.filename or "file").suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(400, f"Only PDF and image files accepted. Got: {ext or 'no extension'}")

        content = await file.read()
        if len(content) == 0:
            raise HTTPException(400, "Empty file")
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(400, f"File too large. Max size: {MAX_FILE_SIZE // (1024*1024)}MB")

        rid = str(uuid.uuid4())
        dest = UPLOAD_DIR / f"{rid}{ext}"
        dest.write_bytes(content)

        filetype = "pdf" if ext == ".pdf" else "image"
        now = datetime.now(timezone.utc).isoformat()

        conn = get_db()
        try:
            conn.execute(
                "INSERT INTO reports (id, patient_id, filename, filepath, filetype, shared_at) VALUES (?,?,?,?,?,?)",
                (rid, patient_id, file.filename, str(dest), filetype, now),
            )
            conn.commit()
        except Exception as db_error:
            try:
                dest.unlink(missing_ok=True)
            except Exception:
                pass
            raise HTTPException(500, f"Database error: {str(db_error)}")
        finally:
            conn.close()

        # Kick off automatic OCR in a daemon thread (printed→PaddleOCR,
        # handwritten→Qwen-VL).  We deliberately use a bare thread instead of
        # FastAPI's BackgroundTasks so the heavy synchronous OCR work does not
        # block the ASGI worker thread (which starves subsequent requests and
        # causes "Failed to fetch" in the frontend).
        from services.pipeline_service import process_report_automatic
        threading.Thread(target=process_report_automatic, args=(rid,), daemon=True).start()

        return {"report_id": rid, "filename": file.filename}

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, f"Upload failed: {str(e)}")


@router.get("/api/test/reports")
def test_reports():
    """List reports for the default patient — no auth token required."""
    patient_id = _default_patient_id()
    conn = get_db()
    rows = conn.execute(
        "SELECT id, filename, filetype, shared_at, analyzed FROM reports WHERE patient_id=? ORDER BY shared_at DESC",
        (patient_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
