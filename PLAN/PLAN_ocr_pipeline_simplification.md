# PLAN: OCR Pipeline Simplification — Remove Multi-OCR, Fix to PaddleOCR + Qwen2.5-VL

---

## SECTION A — GOAL DEFINITION

### What is being built / changed?
The current codebase contains a **pluggable multi-OCR system** that exposes Tesseract, PyMuPDF, EasyOCR, Google Vision, AWS Textract, Azure AI, and a custom HTTP endpoint alongside PaddleOCR and Qwen2.5-VL. This complexity causes confusion, bugs, and unnecessary code paths.

The goal is to **gut every non-pipeline OCR option** and hard-wire the flow to:
> `Doctor clicks "Analyze"` → **DocumentClassifier** decides `printed | handwritten` → `printed` routes to **PaddleOCR (GPU)** / `handwritten` routes to **Qwen2.5-VL (GPU)** → OCR text + structured results returned → displayed inline in the DoctorPortal.

### What does "done" look like?
1. **Backend**: Only `AutoOCRProvider` is the OCR path. `PyMuPDFOCR`, `TesseractOCR`, `CustomHTTPOCR` classes and their `OCR_ENGINES` registrations are removed. The `/api/doctor/analyze` endpoint auto-classifies and runs the correct OCR without any `ocr_provider_id` selection by the user.
2. **Frontend – DoctorPortal**: The "Pipeline" bar with OCR selector dropdown is removed. Clicking "Analyze" immediately shows a step-by-step status indicator (`Classifying → Running OCR → Done`) and renders the full OCR text + structured results **inline** in the report card.
3. **Frontend – OCRWorkbench**: The "Engines" tab listing Tesseract, EasyOCR, Google Vision, etc. is removed or replaced with a read-only display of the fixed pipeline.
4. The `Settings` page no longer allows adding arbitrary OCR providers — only the fixed pipeline is shown.

### Explicitly out of scope
- Changing AI (Gemini/OpenAI) providers — those stay.
- Changing the patient upload flow.
- Changing the database schema beyond what is needed.
- Rewriting the document classifier or OCR models themselves.

---

## SECTION B — TECH STACK

| Layer | Tech | Touches This Task? |
|---|---|---|
| Backend API | Python / FastAPI | YES — main.py (2184 lines) |
| OCR – Printed | PaddleOCR GPU (paddle_ocr_provider.py) | Keep, no changes to internal logic |
| OCR – Handwritten | Qwen2.5-VL (qwen_vl_provider.py) | Keep, no changes to internal logic |
| Document Classifier | MobileNetV3 / CV heuristic (document_classifier.py) | Keep, no changes needed |
| Image Pre-processing | OpenCV (image_processing.py) | Keep as-is |
| Frontend | React + TypeScript (Vite) | YES — DoctorPortal.tsx, OCRWorkbench.tsx, api.ts |
| Database | SQLite (medapp.db) | Minor — providers table cleanup optional |
| Styling | Vanilla CSS (styles.css) | Minor additions for pipeline status UI |

**Decision**: Keep `AutoOCRProvider` as the single OCR dispatch class. Remove all other `OCRProvider` subclasses from `main.py`. Lock `build_ocr` factory to only instantiate `AutoOCRProvider`.

---

## SECTION C — SESSION MODULARIZATION

---

### Session 1: Backend — Remove Dead OCR Provider Classes and Registry

**OBJECTIVE**: Delete all non-pipeline OCR classes and clean the `OCR_ENGINES` dict so only `pipeline`/`auto` remains.

**SCOPE — Exact file and line ranges to touch:**

| File | Lines | Action |
|---|---|---|
| `backend/main.py` | L408–L415 | DELETE `PyMuPDFOCR` class |
| `backend/main.py` | L417–L436 | DELETE `TesseractOCR` class |
| `backend/main.py` | L438–L447 | KEEP `PaddleOCRProviderWrapper` (used by AutoOCRProvider) |
| `backend/main.py` | L449–L467 | KEEP `QwenVLProviderWrapper` (used by AutoOCRProvider) |
| `backend/main.py` | L639–L654 | DELETE `CustomHTTPOCR` class |
| `backend/main.py` | L741–L784 | REPLACE `OCR_ENGINES` dict — keep only `"pipeline"` and `"auto"` entries; remove `pymupdf`, `tesseract`, `paddleocr` direct, `qwen_vl` direct, `custom_http` |
| `backend/main.py` | L792–L796 | SIMPLIFY `build_ocr()` — always return `AutoOCRProvider()`; raise HTTPException(400) for any unrecognised engine |
| `backend/main.py` | L556–L563 | REMOVE the `paddle_endpoint` / `CustomHTTPOCR` branch inside `AutoOCRProvider._route()` — always use `_get_paddle_wrapper()` for printed docs |

**OUTPUT**: `main.py` with ~100 fewer lines; `PyMuPDFOCR`, `TesseractOCR`, `CustomHTTPOCR` gone; `AutoOCRProvider` is the only dispatch class.

**CONNECTS TO**: Session 2 depends on `AutoOCRProvider` being the guaranteed return value of any OCR call.

**FAILURE SURFACE**:
- `fitz` (PyMuPDF) is still used in `_extract_images()` at L2036–L2042 for AI image extraction — do NOT remove the `fitz` import or that function.
- `AutoOCRProvider._route()` at L561–L563 calls `CustomHTTPOCR` for `paddle_endpoint` — must remove that branch or it will crash after deleting the class.

---

### Session 2: Backend — Simplify `/api/doctor/analyze` and Fix Double-Classification Bug

**OBJECTIVE**: Make the analyze endpoint always use `AutoOCRProvider`. Fix the double-classification bug. Return `doc_type`, `ocr_engine`, and `structured_results` so the frontend can display them inline.

**SCOPE — Exact file and line ranges to touch:**

| File | Lines | Action |
|---|---|---|
| `backend/main.py` | L861–L865 | UPDATE `AnalyzeReq` — keep `ocr_provider_id` field for backward compat but ignore it in the handler |
| `backend/main.py` | L2059–L2117 | REFACTOR `analyze_report()` |
| `backend/main.py` | L2070–L2076 | REPLACE provider DB lookup with hardcoded `ocr = AutoOCRProvider()` |
| `backend/main.py` | L2088–L2096 | ADD structured results extraction — after `extract_text()`, call `ocr.extract_structured()` reusing the cached route result; store in DB via `structured_results` column |
| `backend/main.py` | L2111–L2117 | EXTEND return payload: add `doc_type`, `structured_results`, `ocr_engine` fields |
| `backend/main.py` | L552–L577 | FIX double-classification bug in `AutoOCRProvider` — cache `(doc_type, provider)` tuple from `_route()` as instance vars `_last_doc_type` and `_last_provider` so `extract_structured()` reuses them without re-running the classifier |
| `backend/main.py` | L587–L636 | UPDATE `process_report_automatic()` — replace the `_get_provider_row` / `build_ocr` logic with a hardcoded `ocr = AutoOCRProvider()` |

**OUTPUT**: `analyze_report()` always uses the dual pipeline; response shape is `{ analysis, ocr_text, doc_type, structured_results, ocr_engine, report_id, status }`. No double classification.

**CONNECTS TO**: Session 3 (frontend) depends on this exact response shape.

**FAILURE SURFACE**:
- `extract_structured()` called after `extract_text()` currently calls `_route()` again (second classification). The cache fix must happen before calling either method.
- `_migrate_reports_schema()` at L2062 is already called — `structured_results` column exists if it was added by Session 1.

---

### Session 3: Backend — Clean `/api/providers/engines` and Add CRUD Guard

**OBJECTIVE**: Strip the engines list to only the dual pipeline for OCR. Prevent the DB from accepting Tesseract/EasyOCR/etc. providers.

**SCOPE — Exact file and line ranges to touch:**

| File | Lines | Action |
|---|---|---|
| `backend/main.py` | L1974–L2021 | REPLACE `list_engines()` — in the `"ocr"` array keep only a single entry: `{ "id": "pipeline", "name": "MedVault Dual Pipeline (PaddleOCR + Qwen2.5-VL)", "fields": [] }` |
| `backend/main.py` | L1917–L1951 | ADD validation in `create_provider()`: if `req.kind == "ocr"` and `req.engine not in ("pipeline", "auto")`, raise HTTP 400 |

**OUTPUT**: `GET /api/providers/engines` returns one OCR option. New OCR providers with legacy engines are rejected.

**CONNECTS TO**: Session 4 (frontend) — if Settings fetches engines dynamically from this endpoint, cleanup is automatic.

**FAILURE SURFACE**:
- Old rows in the SQLite `providers` table with `engine='tesseract'` still exist and will be served by `listProviders()`. Deal with this in Session 7 (DB cleanup).

---

### Session 4: Frontend — DoctorPortal: Remove OCR Selector, Add Pipeline Status UI

**OBJECTIVE**: Remove the OCR provider dropdown. Add a step-by-step status indicator. Display OCR text, doc type, engine used, and structured results inline in the report card.

**SCOPE — Exact file and line ranges to touch:**

| File | Lines | Action |
|---|---|---|
| `frontend/src/pages/DoctorPortal.tsx` | L21–L25 | REMOVE `providers`, `selectedOCR`, `ocrProviders` state; keep `selectedAI`, `fallbackKey` |
| `frontend/src/pages/DoctorPortal.tsx` | L32–L38 | REMOVE `api.listProviders()` OCR filter; keep only AI provider fetch |
| `frontend/src/pages/DoctorPortal.tsx` | L60–L80 | REFACTOR `handleAnalyze()` — remove `ocrProviderId` from the request; add `pipelineStep` state transitions: `classifying` → `ocr` → `analyzing` → `done` |
| `frontend/src/pages/DoctorPortal.tsx` | L149–L181 | REPLACE the "Pipeline bar" section — remove OCR `<select>` dropdown; replace with a read-only badge: `"Auto-Detect → PaddleOCR (printed) | Qwen2.5-VL (handwritten)"` |
| `frontend/src/pages/DoctorPortal.tsx` | L218–L224 | UPDATE Analyze button to show current step label while processing |
| `frontend/src/pages/DoctorPortal.tsx` | L251–L257 | EXTEND the `expandedReport` panel — add: `doc_type` badge (Printed / Handwritten), `ocr_engine` tag, structured results table (test name / value / reference range), then AI analysis markdown |
| `frontend/src/api.ts` | L48–L49 | UPDATE `analyzeReport()` response type to include `doc_type: string`, `structured_results: any[]`, `ocr_engine: string` |

**New state to add in DoctorPortal.tsx:**
```tsx
const [pipelineStep, setPipelineStep] = useState<
  "idle" | "classifying" | "ocr" | "analyzing" | "done"
>("idle");
const [docType, setDocType] = useState<string>("");
const [structuredResults, setStructuredResults] = useState<Record<string, any[]>>({});
```

**OUTPUT**: Clean pipeline bar; step animation during analysis; inline OCR + structured data after completion.

**CONNECTS TO**: Session 5 (OCRWorkbench) is independent but shares the same mental model.

**FAILURE SURFACE**:
- `handleAnalyze` at L61–L62 checks `!hasAI && !fallbackKey` — keep this guard.
- The `analyzeReport` API call at `api.ts` L48–L49 must match the updated backend response shape from Session 2.

---

### Session 5: Frontend — OCRWorkbench: Remove Multi-Engine UI, Show Fixed Pipeline

**OBJECTIVE**: Replace the selectable engine grid and compare tab with a read-only pipeline diagram.

**SCOPE — Exact file and line ranges to touch:**

| File | Lines | Action |
|---|---|---|
| `frontend/src/pages/OCRWorkbench.tsx` | L12–L18 | REMOVE `"engines"` and `"compare"` from the `Tab` type union |
| `frontend/src/pages/OCRWorkbench.tsx` | L63–L71 | REMOVE `{ key: "engines", ... }` and `{ key: "compare", ... }` from `TABS` array |
| `frontend/src/pages/OCRWorkbench.tsx` | L81–L91 | REPLACE `ENGINES` array — keep only PaddleOCR and Qwen-VL entries, remove Tesseract, EasyOCR, Google, Textract, Azure, Custom |
| `frontend/src/pages/OCRWorkbench.tsx` | L186–L189 | REMOVE `selectedEngine` and `compareEngines` state |
| `frontend/src/pages/OCRWorkbench.tsx` | L235–L261 | REPLACE `renderEngines()` — show a static dual-pipeline diagram instead of a selectable engine grid |
| `frontend/src/pages/OCRWorkbench.tsx` | Full `renderCompare()` function | DELETE entirely |

**OUTPUT**: OCRWorkbench only shows the fixed pipeline; no engine selection confusion.

**CONNECTS TO**: Nothing depends on this for pipeline function — UI-only cleanup.

**FAILURE SURFACE**:
- The `Tab` type change must be reflected in all `tab === "engines"` or `tab === "compare"` branches in the render switch — remove those branches.

---

### Session 6: Frontend — Settings Page: Lock OCR to Pipeline Only

**OBJECTIVE**: In `Settings.tsx`, restrict OCR engine choice to only `"pipeline"`.

**SCOPE:**
- Search `Settings.tsx` for any `engine` dropdown or OCR engine selection UI.
- If it dynamically fetches from `/api/providers/engines`, Session 3's backend fix handles it automatically — verify this is the case.
- If it has hardcoded engine options, replace them with a single read-only `"MedVault Dual Pipeline"` label.

**OUTPUT**: Settings shows a locked OCR pipeline; only AI providers are user-configurable.

**FAILURE SURFACE**:
- If Settings renders engines dynamically from the backend, no code change is needed here — just confirm it.

---

### Session 7: Integration Testing and DB Cleanup

**OBJECTIVE**: End-to-end verification; remove stale legacy provider rows from DB.

**STEPS:**
1. Restart backend — check logs for PaddleOCR GPU warmup and Qwen model load.
2. Log in as doctor → select patient → click Analyze on a printed report → verify `doc_type=printed` + PaddleOCR result displayed inline.
3. Repeat with handwritten report → verify `doc_type=handwritten` + Qwen-VL output displayed.
4. Confirm Settings page shows no Tesseract/EasyOCR options.
5. Run SQLite query: `DELETE FROM providers WHERE kind='ocr' AND engine NOT IN ('pipeline','auto');`
6. Re-run tests after DB cleanup.

**OUTPUT**: Working end-to-end flow; no dead code paths; clean UI; clean DB.

**FAILURE SURFACE**:
- If `process_report_automatic` background task still references old provider rows (before Session 2 fix), it may fail silently — check `status` column in `reports` table.

---

## SECTION D — PROGRESS CHECKLIST

- [ ] **Session 1: Remove Dead OCR Provider Classes**
  - [ ] `PyMuPDFOCR` class deleted (main.py L408–L415)
  - [ ] `TesseractOCR` class deleted (main.py L417–L436)
  - [ ] `CustomHTTPOCR` class deleted (main.py L639–L654)
  - [ ] `OCR_ENGINES` dict cleaned to only `pipeline`/`auto` (main.py L741–L784)
  - [ ] `AutoOCRProvider._route()` paddle_endpoint branch removed (main.py L556–L563)
  - [ ] `build_ocr()` simplified (main.py L792–L796)
  - [ ] Backend starts without ImportError or AttributeError

- [ ] **Session 2: Simplify `/api/doctor/analyze` Endpoint**
  - [ ] `analyze_report()` always uses `AutoOCRProvider()` (main.py L2070–L2076)
  - [ ] `structured_results` extracted and stored (main.py L2088–L2096)
  - [ ] Response payload includes `doc_type`, `structured_results`, `ocr_engine`
  - [ ] `process_report_automatic()` updated to always use `AutoOCRProvider()` (main.py L587–L636)
  - [ ] Double-classification bug fixed in `AutoOCRProvider` (main.py L552–L577)
  - [ ] Curl/browser test of `/api/doctor/analyze` returns correct shape

- [ ] **Session 3: Clean `/api/providers/engines` and CRUD**
  - [ ] `list_engines()` OCR array has only `"pipeline"` entry (main.py L1974–L2000)
  - [ ] `create_provider()` rejects non-pipeline OCR engines (main.py L1917–L1951)
  - [ ] GET `/api/providers/engines` returns exactly 1 OCR option

- [ ] **Session 4: DoctorPortal — Pipeline Status UI**
  - [ ] OCR provider dropdown removed from Pipeline bar (DoctorPortal.tsx L149–L181)
  - [ ] `pipelineStep` state added and drives button/status display
  - [ ] Step indicator (Classify → OCR → AI Analysis) renders during processing
  - [ ] Expanded report panel shows `doc_type` badge + `ocr_engine` + structured results table + AI analysis
  - [ ] `handleAnalyze()` sends request without `ocrProviderId`
  - [ ] `api.ts` response type updated (api.ts L48–L49)
  - [ ] Frontend builds without TypeScript errors

- [ ] **Session 5: OCRWorkbench — Fixed Pipeline Display**
  - [ ] `"engines"` and `"compare"` tabs removed from `TABS` (OCRWorkbench.tsx L63–L71)
  - [ ] `ENGINES` array has only PaddleOCR and Qwen-VL entries (OCRWorkbench.tsx L81–L91)
  - [ ] `renderEngines()` replaced with pipeline diagram
  - [ ] `renderCompare()` deleted
  - [ ] No dead tab reference in render logic

- [ ] **Session 6: Settings — Lock OCR to Pipeline**
  - [ ] OCR engine dropdown in Settings shows only "Dual Pipeline" or is read-only
  - [ ] No Tesseract/EasyOCR/Google Vision options visible in Settings

- [ ] **Session 7: Integration Testing**
  - [ ] Backend restarts clean with GPU warmup logs
  - [ ] Printed report → `doc_type=printed` + PaddleOCR result shown inline
  - [ ] Handwritten report → `doc_type=handwritten` + Qwen-VL result shown inline
  - [ ] Settings page shows no legacy OCR engines
  - [ ] Stale OCR provider rows removed from `providers` table
  - [ ] `process_report_automatic` background task works correctly

---

> **IMPORTANT**: Start with Session 1 only after confirming this plan. Do NOT combine sessions in one response.

> **WARNING**: The `fitz` import must NOT be removed — it is still used by `_extract_images()` at main.py L2036–L2042 which feeds images to the AI provider.

> **ASSUMPTION**: The `process_report_automatic` background task (L587) should also be locked to `AutoOCRProvider` — confirm this before Session 2.
