# MedVault — Codebase Reference Documentation

> **Purpose:** Developer reference for the MedVault medical OCR pipeline.  
> **Last updated:** 2026-07-17  
> **Stack:** Python 3.12 · FastAPI · React 19 · TypeScript · SQLite · PaddleOCR · Qwen2.5-VL

---

## 1. Project Overview

MedVault is a modular medical document OCR pipeline that:
1. Accepts medical-lab image uploads from patients.
2. Classifies each image as **TABLE**, **HANDWRITTEN**, or **PRINTED_TEXT**.
3. Routes the image to the appropriate OCR engine.
4. Extracts structured lab results.
5. Validates and diagnoses abnormal values.
6. Optionally generates a doctor-facing summary and evaluation metrics.

The system is split into a **FastAPI backend** and a **React/TypeScript frontend**, with a SQLite database for persistence.

---

## 2. Repository Layout

```
pipeline_v1/
├── backend/                    # FastAPI application
│   ├── main.py                 # App entry, lifespan, route registration
│   ├── config.py               # Centralised settings (pydantic-settings)
│   ├── auth.py                 # JWT auth, password hashing
│   ├── database.py             # SQLite connection factory + migrations
│   ├── schemas.py              # Pydantic request/response models
│   ├── document_classifier.py  # Re-export shim → backend.classifier
│   ├── paddle_ocr_provider.py  # PaddleOCR GPU backend (printed + tables)
│   ├── qwen_vl_provider.py     # Qwen2.5-VL backend (handwritten)
│   ├── gpu_manager.py          # GPU model preloading / status
│   ├── heuristics.py           # Structured extraction heuristics
│   ├── image_processing.py     # Preprocessing (deskew, enhance, normalize)
│   ├── unit_normaliser.py      # Lab value unit normalisation
│   ├── hepatology_kb.py        # Hepatology knowledge base
│   ├── medical_rules.json      # Medical validation rules
│   ├── labels.json             # Classification label definitions
│   ├── ocr_printed.json        # Printed OCR config
│   ├── ocr_handwritten.json    # Handwritten OCR config
│   ├── agents/                 # Agentic pipeline nodes
│   │   ├── preprocessing_agent.py
│   │   ├── classification_agent.py
│   │   ├── ocr_router_agent.py
│   │   ├── printed_ocr_agent.py
│   │   ├── table_ocr_agent.py
│   │   ├── handwritten_ocr_agent.py
│   │   ├── extraction_agent.py
│   │   ├── validation_agent.py
│   │   ├── diagnosis_agent.py
│   │   ├── summary_agent.py
│   │   ├── evaluation_agent.py
│   │   ├── ocr_result.py
│   │   └── pipeline_v1_AGENTS.md
│   ├── classifier/             # CNN classifier (MobileNetV3 + heuristics)
│   ├── ocr/                    # OCR provider implementations
│   │   └── providers/
│   │       ├── paddle_provider.py
│   │       └── qwen_provider.py
│   ├── preprocessing/          # Image preprocessing modules
│   ├── extraction/             # Structured extraction logic
│   ├── routes/                 # FastAPI routers
│   │   ├── auth_routes.py
│   │   ├── patient_routes.py
│   │   ├── doctor_routes.py
│   │   ├── reports_routes.py
│   │   ├── admin_routes.py
│   │   ├── evaluation_routes.py
│   │   └── pipeline_routes.py
│   ├── services/               # Business logic services
│   │   ├── ocr_service.py      # OCR provider layer + AutoOCRProvider
│   │   ├── pipeline_service.py # Unified DAG runner + PipelineGraph
│   │   └── ai_service.py       # AI analysis / summary generation
│   ├── uploads/                # Uploaded report images
│   └── weights/                # Trained classifier weights (.pth)
├── frontend/                   # React + TypeScript SPA
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx             # Root router + theme
│   │   ├── api.ts              # API client
│   │   ├── pages/              # Page-level components
│   │   ├── components/         # Shared UI components
│   │   └── styles.css          # Neumorphic theme
│   ├── index.html
│   ├── package.json
│   ├── tsconfig.json
│   └── vite.config.ts
├── tests/                      # pytest test suite
├── scripts/                    # Training / evaluation / tuning scripts
├── notebooks/                  # Jupyter exploration notebooks
├── evaluation/                 # Benchmark + metrics
├── eval_reports/               # Generated evaluation reports
├── PLAN/                       # Historical planning documents
├── pipeline.py                 # Top-level pipeline script
├── start.ps1 / start.sh        # Setup scripts
├── Dockerfile
├── requirements.txt            # Root requirements (Python 3.12)
└── README.md
```

---

## 3. Backend Architecture

### 3.1 Entry Point — `backend/main.py`

- Creates the FastAPI app with CORS middleware.
- Registers all routers under `app.include_router(...)`.
- **Lifespan hook** (`lifespan`):
  - Checks CUDA availability (Qwen requires GPU).
  - Creates `uploads/` directory.
  - Initialises SQLite database (`init_db()`).
  - Seeds a default test patient for no-auth test endpoints.
  - Optionally preloads heavy models onto GPU in a background thread.

### 3.2 Configuration — `backend/config.py`

Uses `pydantic-settings` (`BaseSettings`) to centralise all environment variables:

| Field | Env var | Default | Description |
|-------|---------|---------|-------------|
| `jwt_secret` | `JWT_SECRET` | `dev-secret-change-me` | JWT signing key |
| `algorithm` | — | `HS256` | JWT algorithm |
| `access_token_expire_hours` | — | `72` | Token lifetime |
| `db_path` | — | `./medapp.db` | SQLite database path |
| `upload_dir` | — | `./uploads` | Upload storage directory |
| `static_dir` | — | `./frontend/dist` | Built frontend bundle |

### 3.3 Database — `backend/database.py`

- Uses `aiosqlite` for async SQLite access.
- Schema migrations handled by `_migrate_reports_schema()`.
- Key tables: `patients`, `doctors`, `reports`, `ocr_provider_configs`, `schema_version`.
- Connection factory: `get_db()` returns an `aiosqlite.Connection` with `row_factory = aiosqlite.Row`.

### 3.4 Authentication — `backend/auth.py`

- Password hashing: PBKDF2 with bcrypt (`passlib`).
- JWT tokens: `python-jose` with HS256.
- Endpoints: patient register/login, doctor register/login.

---

## 4. Agentic Pipeline (Session 8)

The pipeline is orchestrated by `PipelineGraph` in `backend/services/pipeline_service.py`. It is a **dependency-free DAG runner** (LangGraph-style) that executes nodes in topological order.

### 4.1 Pipeline Stages

```
Preprocess → Classify → OCR → Extract → Validate → Diagnose → [Summary] → [Evaluate]
```

| Stage | Agent | Description |
|-------|-------|-------------|
| Preprocess | `PreprocessingAgent` | Deskew, enhance, normalize image |
| Classify | `ClassificationAgent` | 3-class CNN + heuristic ensemble |
| OCR | `run_ocr()` via `OCR Router` | Dispatch to TABLE / HANDWRITTEN / PRINTED agent |
| Extract | `ExtractionAgent` | Parse structured lab results from OCR text |
| Validate | `ValidationAgent` | Validate against medical rules |
| Diagnose | `DiagnosisAgent` | Identify abnormal values, urgent flags |
| Summary | `SummaryAgent` | Doctor-facing narrative summary (optional) |
| Evaluate | `EvaluationAgent` | CER / accuracy metrics (optional) |

### 4.2 PipelineGraph

```python
class PipelineGraph:
    def add_node(name: str, fn: Callable) -> PipelineGraph
    def add_edge(src: str, dst: str) -> PipelineGraph
    def run(initial_state: dict) -> dict
```

- Nodes are `callable(state: dict) -> Optional[dict]`.
- Edges define execution order.
- Executed via **Kahn's algorithm** (topological sort).
- Node failures are captured in `state["errors"]` without crashing the run.

### 4.3 PipelineResult

Serialisable dataclass returned by `run_pipeline()`:

```python
@dataclass
class PipelineResult:
    preprocessing: Dict[str, Any]
    classification: Dict[str, Any]
    ocr: Dict[str, Any]
    lab_report: Dict[str, Any]
    diagnosis: Dict[str, Any]
    summary: Optional[Dict[str, Any]]
    evaluation: Optional[Dict[str, Any]]
    metadata: Dict[str, Any]
```

---

## 5. OCR System

### 5.1 Document Classification

- **Model:** MobileNetV3-Large CNN + heuristic feature ensemble.
- **Classes:** `TABLE`, `HANDWRITTEN`, `PRINTED_TEXT`.
- **Weights:** `backend/weights/classifier_3class.pth`.
- **Accuracy:** ~77.4% on the 93-image labeled dataset.
- **Heuristic features:** Hough line density, stroke-width variance, connected-component stats, run-length distribution, morphological grid score, Y-projection periodicity.

### 5.2 OCR Providers

| Engine | Provider Class | Use Case | Backend |
|--------|---------------|----------|---------|
| PaddleOCR | `PaddleOCRProvider` | PRINTED_TEXT, TABLE | GPU (CUDA 12.9) |
| PP-Structure | `PaddleOCRProvider` (table mode) | TABLE | GPU (CUDA 12.9) |
| Qwen2.5-VL | `QwenVLProvider` | HANDWRITTEN | GPU (CUDA 12.9) |

### 5.3 AutoOCRProvider (`backend/services/ocr_service.py`)

- Caches classifier, Paddle, and Qwen wrappers as module-level singletons (thread-safe).
- Routes based on 3-class prediction:
  - `HANDWRITTEN` → Qwen2.5-VL
  - `TABLE` / `PRINTED_TEXT` → PaddleOCR
- Fallback: if PaddleOCR fails, falls back to Qwen-VL for printed/table docs.

### 5.4 OCR Router Agent (`backend/agents/ocr_router_agent.py`)

```python
AGENT_FACTORIES = {
    "TABLE": _make_table_agent,
    "HANDWRITTEN": _make_handwritten_agent,
    "PRINTED_TEXT": _make_printed_agent,
    "printed": _make_printed_agent,        # legacy alias
    "handwritten": _make_handwritten_agent, # legacy alias
}
```

Each factory is a zero-arg callable returning a ready agent instance (test-friendly).

---

## 6. GPU Management

### 6.1 Preloading (`backend/gpu_manager.py`)

- `preload_models(blocking=False)`: Eagerly loads classifier CNN + PaddleOCR + Qwen-VL onto GPU in a background thread.
- `gpu_status()`: Returns dict with `cuda_available`, `classifier_loaded`, `paddle_loaded`, `qwen_loaded`, etc.

### 6.2 Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PADDLE_USE_GPU` | `1` (Windows) | Enable Paddle GPU mode |
| `FLAGS_use_gpu` | `1` (Windows) | Paddle GPU flag |
| `MEDVAULT_PRELOAD_GPU` | `1` | Enable eager GPU preloading at startup |
| `QWEN_SERVER_URL` | `http://127.0.0.1:8002/v1/chat/completions` | Qwen-VL server endpoint |
| `QWEN_MODEL_PATH` | — | Path to GGUF model (llama.cpp server) |

---

## 7. Frontend Architecture

### 7.1 Tech Stack

- **React 19** with TypeScript.
- **Vite 6** as build tool.
- **React Router DOM v7** for routing.
- **Lucide React** for icons.
- **react-markdown** for rendered markdown.
- Custom **neumorphic CSS** with dark/light mode.

### 7.2 Routing (`frontend/src/App.tsx`)

Single-page app with view-state routing (no URL-based router for most views):

| View | Component | Description |
|------|-----------|-------------|
| `pick` | `RolePicker` | Choose Patient / Doctor / Settings |
| `patient` | `PatientPortal` | Patient upload + report list |
| `doctor` | `DoctorPortal` | Doctor dashboard + analysis |
| `dashboard` | `Dashboard` | Overview dashboard |
| `settings` | `Settings` | App settings |
| `ocr-workbench` | `OCRWorkbench` | Pipeline run workbench |
| `patient-chart` | `PatientChart` | Individual patient chart |
| `lab-interpret` | `LabInterpretation` | Lab result interpretation |
| `research` | `ResearchPipeline` | Research pipeline view |

### 7.3 API Client (`frontend/src/api.ts`)

- Base URL: `/api`.
- Helper functions: `request()`, `jsonPost()`, `jsonPut()`, `del()`.
- Key exports: `register`, `login`, `uploadReport`, `patientReports`, `runPipeline`, `gpuStatus`, `gpuPreload`, `analyzeReport`, etc.

---

## 8. API Endpoints

### 8.1 Auth

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/patient/register` | Register new patient |
| POST | `/api/patient/login` | Patient login (returns JWT) |
| POST | `/api/doctor/register` | Register new doctor |
| POST | `/api/doctor/login` | Doctor login (returns JWT) |

### 8.2 Patient

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/patient/upload` | Upload medical report (multipart) |
| GET | `/api/patient/reports` | List patient reports |
| GET | `/api/patient/profile` | Get patient profile |
| PUT | `/api/patient/profile` | Update patient profile |

### 8.3 Doctor

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/doctor/patients` | List all patients |
| GET | `/api/doctor/patient/{id}` | Patient detail |
| GET | `/api/doctor/patient/{id}/reports` | Patient reports |
| POST | `/api/doctor/analyze` | Run OCR + AI analysis on report |

### 8.4 Pipeline (Session 8)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/pipeline/run` | Run full pipeline DAG |
| GET | `/api/gpu/status` | GPU / model load status |
| POST | `/api/gpu/preload` | Trigger GPU model preloading |

### 8.5 Test (No-Auth)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/test/upload` | Upload without auth (seeded patient) |
| GET | `/api/test/reports` | List reports for seeded patient |

---

## 9. Database Schema

### 9.1 `patients`

| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT PK | UUID |
| `phone` | TEXT | Phone number (unique) |
| `password_hash` | TEXT | PBKDF2 hash |
| `name` | TEXT | Patient name |
| `created_at` | DATETIME | ISO timestamp |

### 9.2 `doctors`

| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT PK | UUID |
| `phone` | TEXT | Phone number (unique) |
| `password_hash` | TEXT | PBKDF2 hash |
| `name` | TEXT | Doctor name |
| `created_at` | DATETIME | ISO timestamp |

### 9.3 `reports`

| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT PK | UUID |
| `patient_id` | TEXT FK | References `patients.id` |
| `image_hash` | TEXT | SHA256 of original image |
| `image_path` | TEXT | Path to stored image |
| `ocr_provider` | TEXT | `paddleocr` or `qwen_vl` |
| `ocr_raw` | TEXT | Raw OCR JSON |
| `ocr_fields` | TEXT | Validated structured JSON |
| `summary` | TEXT | AI summary text |
| `status` | TEXT | `pending` / `ocr_done` / `summary_done` / `error` |
| `created_at` | DATETIME | Auto timestamp |
| `updated_at` | DATETIME | Auto timestamp |

### 9.4 `ocr_provider_configs`

| Column | Type | Description |
|--------|------|-------------|
| `provider` | TEXT PK | `paddleocr` or `qwen_vl` |
| `config_json` | TEXT | Provider-specific settings |
| `enabled` | INTEGER | 1 = enabled, 0 = disabled |

---

## 10. Key Dependencies

### 10.1 Backend (`backend/requirements.txt`)

| Package | Version | Purpose |
|---------|---------|---------|
| `fastapi` | 0.115.0 | Web framework |
| `uvicorn` | 0.30.6 | ASGI server |
| `pydantic` | 2.9.2 | Data validation |
| `pydantic-settings` | >=2.0.0 | Env config |
| `python-jose[cryptography]` | 3.3.0 | JWT |
| `passlib[bcrypt]` | 1.7.4 | Password hashing |
| `aiosqlite` | 0.20.0 | Async SQLite |
| `paddlepaddle-gpu` | 3.3.1 | PaddlePaddle GPU (CUDA 12.9) |
| `paddleocr` | 2.8.1 | OCR engine |
| `loguru` | >=0.7.0 | Logging |
| `beautifulsoup4` | >=4.12.0 | HTML table parsing |
| `lxml` | >=5.0.0 | XML/HTML parser |
| `deskew` | >=1.5.0 | Image deskewing |
| `PyMuPDF` | >=1.23.0 | PDF parsing |
| `jiwer` | >=3.0.0 | CER/WER metrics |
| `pytest-cov` | >=4.1.0 | Test coverage |

### 10.2 Frontend (`frontend/package.json`)

| Package | Version | Purpose |
|---------|---------|---------|
| `react` | ^19.1.0 | UI library |
| `react-dom` | ^19.1.0 | React DOM renderer |
| `react-router-dom` | ^7.6.2 | Routing |
| `react-markdown` | ^9.0.3 | Markdown rendering |
| `lucide-react` | ^0.511.0 | Icons |
| `vite` | ^6.3.5 | Build tool |
| `typescript` | ^5.8.3 | Type system |

---

## 11. Testing

- **Framework:** pytest.
- **Config:** `pytest.ini`.
- **Test directory:** `tests/`.
- **Key test files:**
  - `test_pipeline_e2e.py` — End-to-end pipeline tests.
  - `test_pipeline_e2e_ibm_spec.py` — IBM spec compliance tests.
  - `test_ocr_agents.py` — OCR agent unit tests.
  - `test_classifier.py` / `test_classifier_module.py` — Classifier tests.
  - `test_backend_units.py` — Backend unit tests.
  - `test_routes_integration.py` — Route integration tests.

---

## 12. Scripts & Notebooks

| Path | Purpose |
|------|---------|
| `scripts/train_classifier.py` | Train the 3-class CNN classifier |
| `scripts/eval_classifier.py` | Evaluate classifier accuracy |
| `scripts/tune_weights.py` | Tune heuristic weights |
| `scripts/diagnose_gpu.py` | GPU diagnostics |
| `scripts/diagnose_features.py` | Feature diagnostics |
| `notebooks/01_preprocessing_exploration.ipynb` | Preprocessing exploration |
| `notebooks/02_classifier_training.ipynb` | Classifier training |
| `notebooks/03_extraction_evaluation.ipynb` | Extraction evaluation |

---

## 13. Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `JWT_SECRET` | No | `dev-secret-change-me` | JWT signing key |
| `GEMINI_API_KEY` | No | — | Google Gemini API key |
| `MEDVAULT_STATIC_DIR` | No | `frontend/dist` | Frontend build directory |
| `MEDVAULT_PRELOAD_GPU` | No | `1` | Enable GPU preloading |
| `QWEN_MODEL_PATH` | No | — | GGUF model path for llama.cpp |
| `QWEN_SERVER_URL` | No | `http://127.0.0.1:8002/v1/chat/completions` | Qwen-VL server |
| `PADDLE_USE_GPU` | No | `1` (Windows) | Paddle GPU mode |
| `FLAGS_use_gpu` | No | `1` (Windows) | Paddle GPU flag |
| `PADDLE_LANG` | No | `en` | PaddleOCR language |
| `PADDLE_TARGET_MAX_DIM` | No | `1600` | Max image dimension |
| `PADDLE_PDF_DPI` | No | `200` | PDF render DPI |
| `PADDLE_MIN_CONF` | No | `0.0` | Min OCR confidence |

---

## 14. Quick Start Commands

```powershell
# Windows
.\start.ps1

# macOS / Linux
chmod +x start.sh && ./start.sh
```

```bash
# Manual backend
python -m venv .venv
.venv\Scripts\pip install -r backend\requirements.txt
.venv\Scripts\uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

# Manual frontend
cd frontend
npm install
npm run dev
```

---

## 15. Important Design Decisions

1. **GPU-first:** PaddleOCR and Qwen-VL run on GPU by default on Windows (CUDA 12.9). CPU fallback is opt-in.
2. **Process isolation:** Paddle and Qwen run in separate processes/microservices to avoid GPU memory conflicts.
3. **Offline-first pipeline:** `PipelineGraph` is dependency-free (no LangGraph/LangChain) so it runs 100% offline.
4. **No-auth test mode:** A seeded default patient enables the Patient Portal without login for testing.
5. **Async SQLite:** All DB access uses `aiosqlite` — never `sqlite3` sync.
6. **Lazy imports:** Heavy OCR/GPU imports are deferred to function scope to keep import-time cheap.

---

## 16. File-to-Responsibility Map

| File | Responsibility |
|------|----------------|
| `backend/main.py` | App factory, lifespan, route registration, static file serving |
| `backend/config.py` | Centralised settings via pydantic-settings |
| `backend/auth.py` | JWT auth, password hashing |
| `backend/database.py` | SQLite connection factory, schema migrations |
| `backend/schemas.py` | Pydantic models for requests/responses |
| `backend/document_classifier.py` | Re-export shim for `backend.classifier` |
| `backend/classifier/` | CNN classifier (MobileNetV3 + heuristics) |
| `backend/paddle_ocr_provider.py` | PaddleOCR GPU backend, PP-Structure table parsing |
| `backend/qwen_vl_provider.py` | Qwen2.5-VL handwritten OCR backend |
| `backend/gpu_manager.py` | GPU preloading, status reporting |
| `backend/heuristics.py` | Structured extraction heuristics |
| `backend/image_processing.py` | Image preprocessing (deskew, enhance) |
| `backend/agents/ocr_router_agent.py` | OCR dispatch router |
| `backend/agents/preprocessing_agent.py` | Preprocessing node |
| `backend/agents/classification_agent.py` | Classification node |
| `backend/agents/extraction_agent.py` | Extraction node |
| `backend/agents/validation_agent.py` | Validation node |
| `backend/agents/diagnosis_agent.py` | Diagnosis node |
| `backend/agents/summary_agent.py` | Summary generation node |
| `backend/agents/evaluation_agent.py` | Evaluation metrics node |
| `backend/services/ocr_service.py` | OCR provider layer, AutoOCRProvider |
| `backend/services/pipeline_service.py` | Pipeline DAG runner, PipelineGraph, PipelineResult |
| `backend/services/ai_service.py` | AI analysis / summary generation |
| `backend/routes/pipeline_routes.py` | `/api/pipeline/run`, `/api/gpu/status`, `/api/gpu/preload` |
| `backend/routes/patient_routes.py` | Patient endpoints |
| `backend/routes/doctor_routes.py` | Doctor endpoints |
| `backend/routes/auth_routes.py` | Auth endpoints |
| `backend/routes/reports_routes.py` | Report CRUD endpoints |
| `backend/routes/admin_routes.py` | Admin/provider config endpoints |
| `backend/routes/evaluation_routes.py` | Evaluation endpoints |
| `frontend/src/App.tsx` | Root component, view routing, theme |
| `frontend/src/api.ts` | API client functions |
| `frontend/src/pages/PatientPortal.tsx` | Patient upload + report list |
| `frontend/src/pages/DoctorPortal.tsx` | Doctor dashboard + analysis |
| `frontend/src/pages/OCRWorkbench.tsx` | Pipeline run workbench |

---

## 17. Common Gotchas

1. **Python version:** Must be **3.12** — the PaddlePaddle CUDA 12.9 wheel is only available for CPython 3.12 on Windows.
2. **GPU required for Qwen:** Qwen2.5-VL has no CPU fallback. If CUDA is unavailable, handwritten OCR will error.
3. **Windows DLL search:** `paddle_ocr_provider.py` calls `_configure_windows_dll_search()` before importing paddle to resolve CUDA/cuDNN DLLs.
4. **No `sqlite3` sync:** All database access must use `aiosqlite`.
5. **Agent factories for tests:** `AGENT_FACTORIES` in `ocr_router_agent.py` enables monkeypatching with fakes in unit tests.
6. **Frontend static serving:** In production, the built frontend is served from `MEDVAULT_STATIC_DIR` (default `frontend/dist`) via `StaticFiles`.

---

*End of reference document.*
