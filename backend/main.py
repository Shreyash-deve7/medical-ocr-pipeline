"""backend/main.py — MedVault Hepatology OCR pipeline FastAPI entry point.

Wires the application:
  * ``CORSMiddleware`` so the Vite dev server (http://localhost:5173) and the
    production SPA bundle can call the API.
  * All seven routers from ``backend/routes/`` via ``app.include_router``.
  * A ``lifespan`` hook that initialises the SQLite schema (``init_db``),
    seeds a default test patient (exposed as the module global
    ``DEFAULT_PATIENT_ID`` which ``reports_routes._default_patient_id`` imports),
    ensures the uploads directory exists, and kicks off background GPU model
    preloading so the GPU status panel flips to "loaded" without blocking
    startup.

Run with:  uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
"""
from __future__ import annotations

import os
import sys
import threading
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

# The routers use bare imports (``from database import ...``, ``from auth import ...``)
# which require the ``backend/`` directory itself on ``sys.path`` — not just the
# project root. When uvicorn loads ``backend.main:app`` from the project root,
# only the project root is on the path, so insert ``backend/`` here before any
# router import. (Tests already do this manually; this makes the live server work.)
_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from database import get_db, init_db

# Module global read by ``routes.reports_routes._default_patient_id``.
DEFAULT_PATIENT_ID: str | None = None


def _seed_default_patient() -> str:
    """Seed a no-auth default patient and return its id (idempotent).

    The Patient Portal UI uses the ``/api/test/*`` endpoints which operate on
    this single seeded patient so uploads work without a login token.
    """
    global DEFAULT_PATIENT_ID
    pid = str(uuid.uuid4())
    phone = "0000000000"  # reserved sentinel phone for the default test patient
    now = datetime.now(timezone.utc).isoformat()
    conn = get_db()
    try:
        row = conn.execute("SELECT id FROM patients WHERE phone=?", (phone,)).fetchone()
        if row:
            DEFAULT_PATIENT_ID = row["id"]
            return DEFAULT_PATIENT_ID
        # password_hash is unused for the test patient but NOT NULL in schema.
        conn.execute(
            "INSERT INTO patients (id, phone, password_hash, name, created_at) VALUES (?,?,?,?,?)",
            (pid, phone, "test$disabled", "Default Test Patient", now),
        )
        conn.commit()
        DEFAULT_PATIENT_ID = pid
        return pid
    finally:
        conn.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init DB, seed default patient, ensure uploads dir, warm GPU."""
    # 1. SQLite schema
    init_db()
    # 2. Default no-auth test patient (sets DEFAULT_PATIENT_ID module global)
    _seed_default_patient()
    print(f"[startup] Default patient id = {DEFAULT_PATIENT_ID}")
    # 3. Uploads directory
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    # 4. Background GPU preload (non-blocking; panel polls /api/gpu/status)
    if os.environ.get("MEDVAULT_SKIP_GPU_PRELOAD") != "1":
        try:
            from gpu_manager import preload_models
            preload_models(blocking=False)
            print("[startup] GPU model preload started in background")
        except Exception as e:  # GPU optional — never block startup on it
            print(f"[startup] GPU preload skipped: {e}")
    yield


app = FastAPI(title="MedVault Hepatology OCR Pipeline", lifespan=lifespan)

# CORS — allow the Vite dev server and the production SPA origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──────────────────────────────────────────────────
from routes.admin_routes import router as admin_router  # noqa: E402
from routes.auth_routes import router as auth_router  # noqa: E402
from routes.doctor_routes import router as doctor_router  # noqa: E402
from routes.evaluation_routes import router as evaluation_router  # noqa: E402
from routes.patient_routes import router as patient_router  # noqa: E402
from routes.pipeline_routes import router as pipeline_router  # noqa: E402
from routes.reports_routes import router as reports_router  # noqa: E402

app.include_router(auth_router)
app.include_router(patient_router)
app.include_router(doctor_router)
app.include_router(reports_router)
app.include_router(pipeline_router)
app.include_router(evaluation_router)
app.include_router(admin_router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
