# SDLC State — MedVault OCR Pipeline (manual mode)

Goal: implement the missing background OCR task contract that goal.md step 3 and
the FastAPI routes already depend on (process_report_automatic + run_pipeline in
backend/services/pipeline_service.py). NVIDIA NIM API is rate-limited/hanging, so
this loop is executed manually by the orchestrator playing all three roles.

| # | Task | Status |
|---|------|--------|
| 1 | Implement `process_report_automatic(report_id)` in pipeline_service.py: classify+route via AutoOCRProvider, update reports row (status/ocr_text/doc_type/ocr_engine/duration), handle errors + retries. | done |
| 2 | Implement `run_pipeline(content, evaluate, summary, use_graph)` in pipeline_service.py used by pipeline_routes.py, reusing the existing agentic DAG. | done |

## Review outcome (manual loop, NIM API down)
- Reviewer: VERDICT CONDITIONAL -> CODER fixed the only Critical (run_pipeline must
  return .to_dict()); verified. Remaining Warning is OUT OF SCOPE: backend/database.py
  is a 19-line SQLAlchemy placeholder missing _migrate_reports_schema/init_db/_notify
  that reports_routes.py + tests import. process_report_automatic guards with an
  inline PRAGMA migration, but the upload path will ImportError before reaching this
  service. Recommend a SEPARATE task to align database.py with the routes/tests.
- Both in-scope tasks marked done.

## Task 3 (separate, requested): align backend/database.py with routes/tests
- CODER: rewrote database.py as raw-sqlite module: DB_PATH (env-overridable),
  get_db()->Connection(Row), init_db() creating all 17 tables from route SQL,
  _migrate_reports_schema/_notify/_audit/_get_provider_row helpers, Base/engine shim
  for models.py. Fixed test INSERTs (NOT-NULL name; real temp file for filepath).
- REVIEWER: VERDICT PASS. All imported symbols present; get_db contract matches
  routes; pytest test_database_migrate_and_helpers + test_pipeline_service_automatic PASS.
- Warning (out of scope, separate task): backend/main.py is still the placeholder
  health app and does NOT mount the routers, so start.ps1's uvicorn backend.main:app
  won't expose /api/patient/upload or /api/pipeline/run. Needs main.py wiring.
- TASK 3 marked done (in-scope).

## Task 4 (requested): GPU OCR + accurate engine switching per doc type
- Goal: PaddleOCR on GPU for PRINTED/TABLE; Qwen2.5-VL on GPU for HANDWRITTEN via
  QWEN_VL_SERVER_URL microservice; confident-gated routing + OCR self-check fallback.
- CODER: rewrote AutoOCRProvider in backend/services/ocr_service.py:
  * _classify() confidence-gated (HANDWRITTEN_CONF_THRESHOLD=0.75, env-overridable);
    below it, downgrade to PaddleOCR (safe GPU default).
  * _route(): HANDWRITTEN->Qwen (server_url microservice if set, else in-process);
    TABLE/PRINTED_TEXT->PaddleOCR (GPU); PaddleOCR-unavailable->Qwen fallback.
  * extract_text hardened to always return str; added _is_empty + self-check that
    retries the other engine when primary returns empty/vision-error.
  * extract_structured aligned with same fallback. QwenVLProviderWrapper reads
    QWEN_VL_SERVER_URL from env when no explicit server_url.
  * Added tests/test_ocr_routing.py (3 tests: printed/table->Paddle,
    handwritten->Qwen when confident, empty-Paddle->Qwen fallback).
- REVIEWER: VERDICT PASS. 3/3 routing tests pass; test_backend_units 33 pass (2
  pre-existing unrelated failures: placeholder main.py, evaluation route).
- TASK 4 marked done.

### How to run the full GPU pipeline (handwritten needs the Qwen microservice)
1. Start Qwen2.5-VL microservice in a SEPARATE CUDA venv (torch CUDA):
   python backend/qwen_vl_server.py   (serves the OpenAI-style /v1/chat/completions)
2. In this backend venv set:
   $env:QWEN_VL_SERVER_URL = "http://localhost:8001/v1/chat/completions"
3. Run OCR:
   & ".venv/Scripts/python.exe" -P -c "import sys; sys.path.insert(0,'backend'); sys.path.append('.'); from services.ocr_service import AutoOCRProvider; ocr=AutoOCRProvider(); print(ocr.extract_text(r'Patient_Kastoor\IMG_xxxx.jpeg','image'))"


## Notes
- DB access uses sqlite `get_db()` from backend.database (raw cursor, no ORM).
- The `reports` table is migrated by `backend.database._migrate_reports_schema`.
- `AutoOCRProvider` lives in backend.services.ocr_service (GPU models lazy-loaded).
- Constraints from goal.md: Python 3.12 + CUDA 12.9 PaddlePaddle; no DirectML, no RapidOCR.
