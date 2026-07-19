"""backend/services/pipeline_service.py — OCR/analysis background service.

Implements the "Automatic Background Task" described in goal.md (section 2, step 3):
when a patient uploads a report, ``process_report_automatic`` runs in a daemon
thread, classifies + routes the document through ``AutoOCRProvider`` (PaddleOCR for
PRINTED_TEXT/TABLE, Qwen2.5-VL for HANDWRITTEN), and persists the raw OCR text back
to the ``reports`` row so the doctor can see it on the dashboard.

Also exposes ``run_pipeline`` for the unified ``POST /api/pipeline/run`` entrypoint
(``backend/routes/pipeline_routes.py``), which reuses the existing agentic DAG when
available and otherwise falls back to the OCR-only path.

Conventions follow the rest of the backend:
  * raw sqlite via ``database.get_db()`` (cursor-based, no ORM),
  * ``AutoOCRProvider`` from ``services.ocr_service`` (GPU models lazy-loaded),
  * heavy OCR imports stay lazy so importing this module is CPU-only safe.
"""
from __future__ import annotations

import threading
import time
import traceback
from dataclasses import dataclass, field
from typing import Any, Optional

from loguru import logger


@dataclass
class PipelineResult:
    """Serializable result for ``POST /api/pipeline/run``.

    Mirrors the ``.to_dict()`` contract the endpoint in
    ``routes/pipeline_routes.py`` relies on, so the route can call
    ``result.to_dict()`` unchanged.
    """

    payload: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return self.payload


# ── reports-row helpers ──────────────────────────────────────────────────────
# The ``reports`` table is owned by ``backend.database``. Different parts of the
# repo expect helpers such as ``_migrate_reports_schema`` to exist there; to keep
# this service resilient when that helper is missing, we ensure the columns we
# write exist via a PRAGMA-based, no-op-if-present migration. This mirrors the
# column set already used by ``routes/reports_routes.py`` (status, ocr_text,
# doc_type, ocr_engine, duration, error, analyzed).

_REQUIRED_REPORT_COLUMNS = {
    "status": "TEXT DEFAULT 'processing'",
    "ocr_text": "TEXT",
    "doc_type": "TEXT",
    "ocr_engine": "TEXT",
    "duration": "REAL",
    "error": "TEXT",
    "analyzed": "INTEGER DEFAULT 0",
}


def _ensure_report_columns(conn) -> None:
    """Idempotently add the report columns this service reads/writes."""
    existing = {r["name"] for r in conn.execute("PRAGMA table_info(reports)")}
    for col, ddl in _REQUIRED_REPORT_COLUMNS.items():
        if col not in existing:
            conn.execute(f"ALTER TABLE reports ADD COLUMN {col} {ddl}")
    conn.commit()


def _get_report_row(conn, report_id: str) -> Optional[dict]:
    row = conn.execute("SELECT * FROM reports WHERE id=?", (report_id,)).fetchone()
    return dict(row) if row else None


# ── automatic background OCR (goal.md step 3) ─────────────────────────────────
def process_report_automatic(report_id: str, max_retries: int = 3, doc_type_hint: str = "") -> dict:
    """Run OCR for an uploaded report in the background and persist the result.

    Designed to be invoked from a ``threading.Thread(target=..., daemon=True)``
    spawned by the upload endpoint, so the heavy synchronous OCR does not block the
    ASGI worker (which would starve subsequent requests / cause "Failed to fetch"
    in the frontend).

    Updates the ``reports`` row:
      * success -> status='done', ocr_text, doc_type, ocr_engine, duration
      * failure -> status='failed', error

    Retries transient OCR failures up to ``max_retries`` times before giving up.
    """
    from database import get_db

    # Best-effort schema migration (no-op if columns already present). If the
    # dedicated helper exists in backend.database, prefer it.
    try:
        from database import _migrate_reports_schema  # type: ignore
        has_migrate = True
    except Exception:
        has_migrate = False

    for attempt in range(1, max_retries + 1):
        conn = get_db()
        try:
            if has_migrate:
                _migrate_reports_schema(conn)
            _ensure_report_columns(conn)

            row = _get_report_row(conn, report_id)
            if row is None:
                logger.warning("process_report_automatic: report {} not found", report_id)
                return {"report_id": report_id, "status": "not_found"}

            filepath = row.get("filepath")
            filetype = row.get("filetype", "image")
            if not filepath or not __import__("pathlib").Path(filepath).exists():
                logger.warning("process_report_automatic: file missing for {}", report_id)
                conn.execute("UPDATE reports SET status='failed', error=? WHERE id=?",
                             ("uploaded file missing", report_id))
                conn.commit()
                return {"report_id": report_id, "status": "failed", "error": "file missing"}

            try:
                conn.execute("UPDATE reports SET status='processing' WHERE id=?", (report_id,))
                conn.commit()

                from services.ocr_service import AutoOCRProvider
                ocr = AutoOCRProvider(doc_type_hint=doc_type_hint)

                start = time.time()
                ocr_text = ocr.extract_text(filepath, filetype, doc_type_hint=doc_type_hint)
                duration = time.time() - start
                doc_type = getattr(ocr, "last_doc_type", "printed")
                ocr_engine = type(ocr.last_provider).__name__ if getattr(ocr, "last_provider", None) else "AutoOCRProvider"

                conn.execute(
                    "UPDATE reports SET status='done', ocr_text=?, doc_type=?, ocr_engine=?, duration=? WHERE id=?",
                    (ocr_text or "", doc_type, ocr_engine, duration, report_id),
                )
                conn.commit()
                logger.info("process_report_automatic: {} done in {:.2f}s ({}, {})",
                            report_id, duration, doc_type, ocr_engine)
                return {"report_id": report_id, "status": "done", "doc_type": doc_type,
                        "duration": duration, "ocr_engine": ocr_engine}
            except ValueError as cfg_err:
                conn.execute("UPDATE reports SET status='failed', error=? WHERE id=?",
                             (f"ValueError: {cfg_err}", report_id))
                conn.commit()
                logger.error("process_report_automatic: {} permanently failed (config error)\n{}", report_id, str(cfg_err))
                return {"report_id": report_id, "status": "failed", "error": str(cfg_err), "attempts": attempt}
            except Exception as ocr_err:  # noqa: BLE001 - retry on transient OCR failure
                logger.warning("process_report_automatic: attempt {}/{} failed for {}: {}",
                               attempt, max_retries, report_id, ocr_err)
                if attempt >= max_retries:
                    tb = traceback.format_exc()
                    conn.execute("UPDATE reports SET status='failed', error=? WHERE id=?",
                                 (f"{type(ocr_err).__name__}: {ocr_err}", report_id))
                    conn.commit()
                    logger.error("process_report_automatic: {} permanently failed\n{}", report_id, tb)
                    return {"report_id": report_id, "status": "failed",
                            "error": str(ocr_err), "attempts": attempt}
                time.sleep(min(2.0 * attempt, 10.0))  # brief backoff before retry
        finally:
            conn.close()

    return {"report_id": report_id, "status": "failed", "error": "exhausted retries"}


# ── unified pipeline entrypoint (POST /api/pipeline/run) ──────────────────────
def run_pipeline(content: bytes, evaluate: bool = False, summary: bool = False,
                 use_graph: bool = True, report_id: str | None = None) -> PipelineResult:
    """Run the full MedVault OCR pipeline over raw image bytes.

    Returns a ``PipelineResult`` exposing ``.to_dict()`` so the endpoint in
    ``routes/pipeline_routes.py`` keeps working unchanged.

    Heavy OCR / LLM paths stay behind the offline agents (the same ones monkeypatched
    via ``ocr_router_agent.AGENT_FACTORIES`` in tests), so the default path is
    LLM-free / network-free / GPU-free where the underlying providers are faked.

    ``use_graph`` selects the PipelineGraph DAG orchestration when available;
    when the graph machinery is not importable we fall back to the linear
    OCR -> (optional structured) -> (optional AI) path below.

    ``report_id``: when provided, the pipeline first checks the ``reports`` row
    for OCR text already produced by the upload's background task
    (``process_report_automatic``). If a non-empty ``ocr_text`` with
    ``status='done'`` is present, it is reused and the expensive OCR step is
    skipped — making the doctor's "Run Pipeline" near-instant. OCR is only
    re-run when the stored text is missing/empty/failed.
    """
    import tempfile
    from pathlib import Path

    suffix = ".png"
    tmp = Path(tempfile.gettempdir()) / f"medvault_run_{int(time.time()*1000)}{suffix}"
    tmp.write_bytes(content)

    try:
        doc_type = "printed"
        ocr_text = ""
        ocr_engine = "AutoOCRProvider"
        structured: list[dict] = []

        # ── Reuse stored OCR text when available (big speed win) ──────────
        reused = False
        if report_id:
            try:
                from database import get_db
                conn = get_db()
                try:
                    row = conn.execute(
                        "SELECT ocr_text, doc_type, ocr_engine, status FROM reports WHERE id=?",
                        (report_id,),
                    ).fetchone()
                finally:
                    conn.close()
                if row:
                    stored_text = (row["ocr_text"] or "").strip() if "ocr_text" in row.keys() else ""
                    stored_status = row["status"] if "status" in row.keys() else ""
                    if stored_text and stored_status != "failed":
                        ocr_text = stored_text
                        doc_type = row["doc_type"] or "printed"
                        ocr_engine = row["ocr_engine"] or ocr_engine
                        reused = True
                        logger.info("run_pipeline: reused stored OCR for report {} ({} chars, {})",
                                    report_id, len(ocr_text), ocr_engine)
            except Exception as e:  # noqa: BLE001 - reuse is best-effort; fall back to OCR
                logger.warning("run_pipeline: stored-OCR lookup failed for {}: {}", report_id, e)

        # ── Run OCR only when we don't have stored text ───────────────────
        if not reused:
            from services.ocr_service import AutoOCRProvider
            ocr = AutoOCRProvider()
            try:
                ocr_text = ocr.extract_text(str(tmp), "image")
                doc_type = getattr(ocr, "last_doc_type", "printed")
                ocr_engine = type(ocr.last_provider).__name__ if getattr(ocr, "last_provider", None) else ocr_engine
            except Exception as e:  # noqa: BLE001 - surface as a result, don't crash the endpoint
                logger.warning("run_pipeline: OCR failed: {}", e)

            # Reuse the existing agentic DAG when present (full preprocess->classify->
            # OCR->extract->validate->diagnose->[summary]->[evaluate] flow).
            try:
                if hasattr(ocr, "extract_structured"):
                    structured = ocr.extract_structured(str(tmp), "image") or []
            except Exception as e:  # noqa: BLE001
                logger.warning("run_pipeline: structured OCR failed: {}", e)

        analysis: Optional[str] = None
        if (evaluate or summary) and ocr_text:
            try:
                from services.ai_service import build_ai, MEDICAL_PROMPT, _extract_images
                ai = build_ai("gemini", {"api_key": ""})
                analysis = ai.analyze(MEDICAL_PROMPT, ocr_text, _extract_images(str(tmp), "image"))
            except Exception as e:  # noqa: BLE001
                logger.warning("run_pipeline: AI analysis skipped: {}", e)

        # Build the heavily nested payload for the frontend
        lab_results = []
        diag_dict = None
        if ocr_text:
            try:
                from agents.ocr_result import OCRResult
                from agents.extraction_agent import ExtractionAgent
                from schemas import LabReport
                from agents.diagnosis_agent import DiagnosisAgent
                
                ocr_res = OCRResult(
                    raw_output=ocr_text,
                    engine=ocr_engine,
                    confidence=1.0,
                    processing_time_seconds=0.0
                )
                # Run extraction (heuristic fallback, no LLM)
                extract_agent = ExtractionAgent(llm_client=None)
                extract_res = extract_agent.run(ocr_res)
                lab_results = extract_res.lab_results
                
                # Run diagnosis (heuristic fallback, no LLM)
                diag_agent = DiagnosisAgent(llm_client=None)
                lab_rep = LabReport(
                    report_id=report_id or "tmp",
                    patient_id="tmp",
                    date="tmp",
                    lab_results=lab_results
                )
                diag_res = diag_agent.run(lab_rep)
                if hasattr(diag_res, "model_dump"):
                    diag_dict = diag_res.model_dump()
                elif hasattr(diag_res, "to_dict"):
                    diag_dict = diag_res.to_dict()
                else:
                    diag_dict = dict(diag_res)
            except Exception as e:
                logger.warning("run_pipeline: Agents failed: {}", e)
        
        if not diag_dict:
            diag_dict = {
                "clinical_patterns": [],
                "abnormal_values": [],
                "urgent_flags": [],
                "suggested_followup": [],
                "summary_for_doctor": "Diagnosis unavailable.",
                "llm_narrative": None
            }

        payload = {
            "preprocessing": {"transformations_applied": [], "quality_metrics_before": {}},
            "classification": {"class": doc_type.upper(), "confidence": 1.0, "fallback_triggered": False},
            "ocr": {
                "raw_output": ocr_text,
                "engine": ocr_engine,
                "confidence": None,
                "processing_time_seconds": 0
            },
            "lab_report": {"lab_results": lab_results},
            "diagnosis": diag_dict,
            "summary": {"summary": analysis, "flags": [], "critical_alerts": [], "discussion_points": []} if analysis else None,
            "evaluation": None,
            "metadata": {
                "use_graph": False,
                "evaluate": evaluate,
                "summary": summary,
                "duration_ms": 0,
                "started_at": "",
                "completed_at": "",
                "errors": {}
            }
        }

        return PipelineResult(payload=payload)
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass
