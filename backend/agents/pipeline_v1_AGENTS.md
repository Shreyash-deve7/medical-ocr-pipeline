# AGENTS.md — pipeline_v1/backend/

## What This Module Owns

This is the **stateful** half of the system. Responsibilities:
- SQLite database (`medapp.db`) — report records, OCR provider configs
- Schema migration via `_migrate_reports_schema()`
- Async DB access via `aiosqlite`
- Receiving OCR results from `server.py` and persisting them
- Calling the summary model and storing the result
- Serving structured report data to the doctor dashboard

This module does NOT do OCR itself — it receives OCR JSON from `server.py`.

---

## Database Schema (medapp.db)

### `reports` table
```sql
CREATE TABLE reports (
    id          TEXT PRIMARY KEY,       -- UUID, generated at upload time
    patient_id  TEXT NOT NULL,
    image_hash  TEXT NOT NULL,          -- SHA256 of original image bytes
    image_path  TEXT NOT NULL,          -- path inside container volume
    ocr_provider TEXT NOT NULL,         -- "paddleocr" | "qwen_vl"
    ocr_raw     TEXT,                   -- raw OCR JSON (unvalidated)
    ocr_fields  TEXT,                   -- validated + structured JSON
    summary     TEXT,                   -- AI summary text
    status      TEXT NOT NULL DEFAULT 'pending',  -- pending|ocr_done|summary_done|error
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### `ocr_provider_configs` table
```sql
CREATE TABLE ocr_provider_configs (
    provider    TEXT PRIMARY KEY,       -- "paddleocr" | "qwen_vl"
    config_json TEXT NOT NULL,          -- JSON blob of provider-specific settings
    enabled     INTEGER DEFAULT 1
);
```

### Migration Rules
- Add columns via `ALTER TABLE ... ADD COLUMN` in `_migrate_reports_schema()`
- Never DROP columns — mark deprecated columns with `_deprecated_` prefix in a comment
- Always run migration at startup before accepting requests
- Schema version is tracked in a `schema_version` table (create it if missing)

---

## Async DB Patterns

Always use the connection as an async context manager:

```python
# CORRECT
async with aiosqlite.connect(DB_PATH) as db:
    db.row_factory = aiosqlite.Row
    async with db.execute("SELECT ...", params) as cursor:
        row = await cursor.fetchone()

# WRONG — do not hold a connection open at module level
db = await aiosqlite.connect(DB_PATH)  # ← never do this
```

For write operations, always `await db.commit()` and handle `IntegrityError` explicitly.

---

## Report Status Flow

```
pending
  │
  ├─[OCR completes]──► ocr_done
  │                        │
  │                   [summary completes]──► summary_done
  │
  └─[any error]──► error  (store error_message in a dedicated column)
```

- Status transitions must be atomic (wrap in a single `UPDATE` with `WHERE status = 'expected_current'`)
- Never skip status — don't jump from `pending` to `summary_done`
- The doctor dashboard should only show reports in `summary_done` state

---

## Summary Generation

### Prompt Template
```python
SUMMARY_SYSTEM_PROMPT = """You are assisting a licensed medical professional reviewing a patient's uploaded medical report.
Do NOT make diagnoses. Do NOT suggest treatments.
Your role: summarize findings, identify values outside normal reference ranges, and list key discussion points.
Format: JSON with keys: summary (string), flags (list of {field, value, normal_range, note}), discussion_points (list of strings).
Respond ONLY with valid JSON. No preamble, no markdown fences."""
```

### Rules
- Always include `report_id` in the summary call for traceability
- Stream the response to the client (SSE) — do not wait for full completion
- If the summary model returns invalid JSON, store the raw text and set `summary_status = 'parse_error'`
- Cap summary at 500 tokens — doctors need dense, not verbose
- Do not pass raw image bytes to the summary model — only the validated `ocr_fields` JSON

---

## API Endpoints (this module)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/reports/{report_id}` | Full report including OCR + summary |
| GET | `/reports/patient/{patient_id}` | All reports for a patient |
| GET | `/reports/{report_id}/stream` | SSE stream of summary generation |
| POST | `/reports/{report_id}/retry` | Retry a failed OCR or summary step |
| GET | `/admin/providers` | List OCR provider configs |
| PATCH | `/admin/providers/{provider}` | Update provider config |

All endpoints return:
```json
{"data": ..., "report_id": "...", "status": "...", "duration_ms": 123}
```

---

## Error Handling

```python
# Always catch at the pipeline boundary, not inside helpers
try:
    result = await run_ocr_step(report_id, image_path)
except OCRTimeoutError:
    await update_report_status(report_id, "error", error_code="OCR_TIMEOUT")
    raise HTTPException(503, detail={"error": "OCR timed out", "code": "OCR_TIMEOUT"})
except OCRLowConfidenceError as e:
    # Don't fail — store with low_confidence flag and proceed
    await store_ocr_result(report_id, e.result, confidence_flag=True)
```

- OCR timeout threshold: **8.0s** (leaves 2s buffer for summary first-token under the 10s e2e budget)
- Low confidence threshold: `< 0.75` confidence score from PaddleOCR / Qwen
- Low confidence reports show a warning in the doctor UI but still proceed

---

## File Layout

```
pipeline_v1/backend/
├── main.py          # FastAPI app, lifespan, route registration
├── routes/
│   ├── reports.py   # Report CRUD endpoints
│   ├── stream.py    # SSE streaming endpoint
│   └── admin.py     # Provider config endpoints
├── services/
│   ├── ocr_client.py    # HTTP client to server.py OCR endpoint
│   ├── summary.py       # Summary model call + streaming
│   └── db.py            # aiosqlite helpers, migration
├── schemas.py           # Pydantic models + validated OCR field definitions
├── config.py            # Env vars, paths, timeouts (no hardcoded values)
└── AGENTS.md            # ← this file
```

---

## What NOT to Do in This Module

- Do not call PaddleOCR or Qwen directly — use `ocr_client.py` which calls `server.py`
- Do not use `sqlite3` (sync) — only `aiosqlite`
- Do not store patient names or PII in log output
- Do not return `ocr_raw` to the frontend — only `ocr_fields` (validated)
- Do not add new DB columns without adding them to `_migrate_reports_schema()`
