from __future__ import annotations

# Per WORKING_GPU_SETUP.md the native CUDA 12.9 wheel (paddlepaddle-gpu 3.3.1)
# runs PaddleOCR on the GPU with no conflicts. GPU is preferred by default.
# Paddle (printed) and Qwen/torch (handwritten) run in SEPARATE processes /
# microservices (Hard Rule #2), so they never share a process. Paddle CPU is
# still opt-in via PADDLE_USE_GPU=0 for low-memory machines.
import os
import platform
# Keep the Windows GPU path enabled unless the user explicitly opts out.
if platform.system() == "Windows":
    os.environ.setdefault("PADDLE_USE_GPU", "1")
    os.environ.setdefault("FLAGS_use_gpu", "1")
    os.environ.pop("CUDA_VISIBLE_DEVICES", None)

import sys

# Ensure sibling modules (config, database, routes, services, document_classifier,
# paddle_ocr_provider, qwen_vl_provider, heuristics) are importable when running
# as ``backend.main:app`` (the modules import each other with bare names).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
import uuid

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from database import init_db, get_db

# ── Route layers ──────────────────────────────────────────────
from routes.auth_routes import router as auth_router
from routes.patient_routes import router as patient_router
from routes.doctor_routes import router as doctor_router
from routes.reports_routes import router as reports_router
from routes.admin_routes import router as admin_router
from routes.evaluation_routes import router as evaluation_router
from routes.pipeline_routes import router as pipeline_router

# ID of the default patient used by the no-login test endpoints. Populated
# during app startup (see ``_seed_default_patient`` in ``lifespan``).
DEFAULT_PATIENT_ID: str | None = None


def _seed_default_patient() -> str:
    """Ensure a default patient row exists and return its id.

    Used by the no-auth test endpoints (``/api/test/*``) so the Patient Portal
    can upload and list reports without any login / token.
    """
    from auth import _hash_pw

    default_phone = "5511999"
    default_name = "Test Patient"
    default_password = "password"
    now = datetime.now(timezone.utc).isoformat()

    conn = get_db()
    try:
        row = conn.execute(
            "SELECT id FROM patients WHERE phone=?", (default_phone,)
        ).fetchone()
        if row:
            return row["id"]
        pid = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO patients (id, phone, password_hash, name, created_at) "
            "VALUES (?,?,?,?,?)",
            (pid, default_phone, _hash_pw(default_password), default_name, now),
        )
        conn.commit()
        print(f"[startup] Seeded default patient '{default_name}' ({pid})")
        return pid
    finally:
        conn.close()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # GPU preflight (Qwen OCR requires CUDA, no CPU fallback)
    try:
        import torch
        if torch.cuda.is_available():
            print(f"[GPU] CUDA ready: {torch.cuda.get_device_name(0)}")
        else:
            print("=" * 64)
            print("[GPU][WARN] CUDA NOT available. Qwen2.5-VL OCR requires a GPU")
            print("and CPU fallback is disabled — handwritten OCR will error.")
            print("=" * 64)
    except ImportError:
        print("[GPU][WARN] torch not installed; Qwen OCR backend unavailable.")

    # Ensure uploads directory exists
    UPLOAD_DIR = Path(__file__).parent / "uploads"
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    
    init_db()

    # Seed a default patient for the no-login test version so the Patient Portal
    # can upload / list reports without any auth token.
    global DEFAULT_PATIENT_ID
    DEFAULT_PATIENT_ID = _seed_default_patient()

    # ── Eagerly preload heavy models onto the GPU at startup ──────────────
    # This warms the NVIDIA GPU (classifier CNN + PaddleOCR + Qwen-VL) so the
    # first OCR request is fast and the GPU isn't idle. Runs in a background
    # thread so the server is ready to accept connections immediately.
    preload_env = os.getenv("MEDVAULT_PRELOAD_GPU", "1")
    if preload_env == "1":
        try:
            from gpu_manager import preload_models
            print("[startup] Preloading GPU models (classifier + PaddleOCR + Qwen-VL)...")
            preload_models(blocking=False)
        except Exception as e:
            print(f"[startup] GPU preload skipped: {e}")

    yield


app = FastAPI(title="MedVault", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register all route layers. Paths are defined in full in each router (no
# prefix), so the public API surface is unchanged from the monolith.
app.include_router(auth_router)
app.include_router(patient_router)
app.include_router(doctor_router)
app.include_router(reports_router)
app.include_router(admin_router)
app.include_router(evaluation_router)
app.include_router(pipeline_router)


# ── Serve frontend ───────────────────────────────────────────
FRONTEND_DIST = Path(os.getenv("MEDVAULT_STATIC_DIR", str(Path(__file__).parent.parent / "frontend" / "dist")))
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="spa")
