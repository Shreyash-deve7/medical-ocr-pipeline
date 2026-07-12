# AGENTS.md — Medical OCR Dashboard (Root)

## Project Purpose
A two-user medical dashboard:
- **Patient** uploads images of medical reports (printed or handwritten)
- **Doctor** receives structured OCR results + AI-generated summary, enabling point-by-point discussion

Performance contract: **every image must complete OCR + summary in ≤ 10 seconds end-to-end.**

---

## Service Map

```
[Patient Browser]
      │ POST /upload
      ▼
[FastAPI server.py :8000]  ← stateless, no DB
      │ routes by image type
      ├─── printed → PaddleOCR (GPU, in-process)
      └─── handwritten → Qwen2.5-VL-3B-Instruct microservice :8002
              │
              ▼
        OCR JSON result
              │
              ▼
[pipeline_v1/backend/main.py :800x]  ← has SQLite (medapp.db), async
      │ stores report record
      │ calls summary model
      ▼
[Doctor Browser]  ← polls or receives SSE with structured result + summary
```

**Ports:**
- `:8000` — FastAPI server (StaticFiles + API)
- `:8002` — Qwen2.5-VL-3B-Instruct microservice
- Static UI lives in `ui/`, served by FastAPI's StaticFiles mount

---

## Directory Structure

```
/
├── server.py                    # Stateless FastAPI app, OCR routing
├── docker-compose.yml           # Two services: ocr-processor, ui-server
├── Dockerfile                   # nvidia/cuda:12.6.0-cudnn-runtime-ubuntu22.04
├── ui/                          # Vanilla HTML/CSS/JS frontend (no framework)
│   ├── patient.html
│   ├── doctor.html
│   └── static/
├── pipeline_v1/
│   ├── backend/
│   │   └── main.py             # Stateful FastAPI: SQLite, report records, provider configs
│   └── ...
├── models/                      # Local model weights (do NOT commit)
├── medapp.db                    # SQLite database (do NOT commit)
└── AGENTS.md                    # ← this file
```

---

## Hard Rules — Never Violate These

1. **Never block the upload request on OCR completion.** Upload → enqueue/background task → return `202 Accepted` with a `report_id`. Doctor dashboard polls or receives SSE.
2. **Never run two GPU-heavy models simultaneously in the same process.** PaddleOCR and Qwen-VL are on the same NVIDIA GPU. Serialize GPU calls or they will OOM.
3. **SQLite only in `pipeline_v1/backend/main.py`.** `server.py` is stateless and must stay that way. Do not add DB calls to `server.py`.
4. **Never hallucinate medical field names.** All structured OCR output fields (e.g. `hemoglobin`, `creatinine`, `bp_systolic`) must match the validated schema in `pipeline_v1/backend/schemas.py`. If that file doesn't exist yet, create it before adding new fields.
5. **Never `pip install` outside the Dockerfile.** All Python dependencies go in `requirements.txt` and are installed at build time. Do not suggest `pip install X` as a fix — instead update `requirements.txt` and rebuild.
6. **Never load model weights inside a request handler.** Models are loaded once at startup (lifespan event or module-level singleton). Loading per-request will blow your 5s budget entirely.
7. **No JavaScript frameworks in `ui/`.** Vanilla JS only. No npm, no bundlers, no CDN React/Vue. Keep it `<script>` tags and native fetch.

---

## OCR Routing Logic

```python
# Decision is made in server.py before dispatching
if image_is_handwritten(image):          # heuristic or explicit flag from patient
    result = await call_qwen_microservice(image)   # POST :8002
else:
    result = await run_paddle_ocr(image)           # in-process GPU call
```

- **PaddleOCR** — printed, structured lab reports, prescriptions with clear fonts
- **Qwen2.5-VL-3B-Instruct** — handwritten notes, cursive, mixed printed/handwritten
- When in doubt, prefer Qwen (higher accuracy, acceptable latency on GPU)
- The routing decision must be logged so it can be audited

---

## Performance Budget (10s target per image — splits flexible, e2e must be ≤ 10.0s)

| Step | Budget |
|---|---|
| Image upload + preprocessing | ≤ 0.5s |
| OCR (PaddleOCR printed) | ≤ 3.0s |
| OCR (Qwen-VL handwritten) | ≤ 5.0s |
| Schema validation + field extraction | ≤ 0.3s |
| AI summary generation (streamed) | ≤ 5.0s (first token < 1.0s) |
| DB write (aiosqlite) | ≤ 0.2s |
| **Total** | **≤ 10.0s** |

If a proposed change would push any step over budget, flag it explicitly before implementing.

---

## Async Rules

- All I/O (DB, HTTP to Qwen microservice, file reads) must be `async/await`
- CPU-bound work (image preprocessing, heuristic classification) goes in `asyncio.run_in_executor(None, fn)` — never block the event loop
- Use `httpx.AsyncClient` for internal service calls, not `requests`
- Never use `time.sleep()` — use `await asyncio.sleep()` if needed

---

## Docker / CUDA Constraints

- Base image: `nvidia/cuda:12.6.0-cudnn-runtime-ubuntu22.04`
- GPU is accessed via docker-compose `device_id` reservation — only `ocr-processor` service has GPU
- Model weights are in named volumes: `ocr-model-cache`, `paddx-model-cache` — do not hardcode absolute paths, use env vars or config
- If you add a new service to `docker-compose.yml`, it does NOT get GPU by default — explicitly add device reservation if needed
- Never store large files (model weights, DB, images) in the image layer

---

## Code Style (Python)

- Python 3.10+, type hints on all function signatures
- FastAPI dependency injection for shared resources (DB session, model instances)
- Pydantic v2 models for all request/response schemas
- Errors return structured JSON: `{"error": "...", "code": "OCR_FAILED", "report_id": "..."}`
- All endpoints have docstrings describing their role in the pipeline
- Log every OCR call: model used, image hash, duration, confidence score

## Code Style (JavaScript)

- ES2020+ (no transpilation needed — modern browsers only)
- `async/await` for all fetch calls, never `.then()` chains
- No global state — use a single `AppState` object per page
- All API calls go through a central `api.js` module, never inline fetch in HTML files

---

## Medical Domain Rules

- OCR output is **always** treated as unverified until schema-validated
- Never display raw OCR text to the doctor without confidence scores
- Summary generation prompt must include: "You are assisting a licensed medical professional. Do not make diagnoses. Summarize findings and flag values outside normal range."
- Patient data is sensitive — no logging of OCR text content to stdout in production mode
- Report images are stored by hash, not by patient name, in the file system
