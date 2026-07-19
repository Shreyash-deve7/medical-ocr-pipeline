"""backend/database.py — raw SQLite data layer for the MedVault backend.

The rest of the backend (all of ``routes/*`` and ``services/pipeline_service.py``)
talks to the database through this module using the stdlib ``sqlite3`` connection
API (``conn.execute(...)``), NOT through SQLAlchemy sessions. This module therefore
provides a connection-based ``get_db()``, schema creation via ``init_db()``, and the
small helper functions the routes/tests import:

    get_db()                 -> sqlite3.Connection
    init_db()                -> create all tables if missing
    _migrate_reports_schema(conn)
    _notify(conn, user_type, user_id, title, body, kind="message")
    _audit(conn, user_type, user_id, action, ref_type, ref_id, details)
    _get_provider_row(conn, provider_id, kind)

``DB_PATH`` can be overridden with the ``DB_PATH`` environment variable (the test
suite does this to redirect to a temp file). ``models.py`` still imports ``Base``
for ORM compatibility; the raw-SQL routes do not use it.

All raw-SQL paths run under Python 3.12 + the CUDA 12.9 PaddlePaddle environment
required by goal.md; this module is pure stdlib and CPU-safe.
"""
from __future__ import annotations

import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from typing import Optional

# SQLAlchemy shim so ``models.py`` (``from database import Base``) keeps importing.
# The routes use raw SQL and never touch this; it exists only for ORM-compat.
try:  # pragma: no cover - sqlalchemy is present in the venv
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker, declarative_base

    Base = declarative_base()
    _engine = create_engine(f"sqlite:///{os.environ.get('DB_PATH', 'medvault.db')}")
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
except Exception:  # pragma: no cover
    Base = None
    SessionLocal = None


DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "medvault.db"))

_lock = threading.Lock()


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row  # rows behave like dicts (routes do dict(row))
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_db() -> sqlite3.Connection:
    """Return a raw sqlite3 connection (the contract every route expects)."""
    return _connect()


def _migrate_patients_schema(conn: sqlite3.Connection) -> None:
    # Safely add missing columns one by one
    columns = [
        "date_of_birth TEXT",
        "gender TEXT",
        "blood_group TEXT",
        "email TEXT",
        "address TEXT",
        "emergency_contact TEXT",
        "emergency_phone TEXT"
    ]
    for col in columns:
        try:
            conn.execute(f"ALTER TABLE patients ADD COLUMN {col}")
        except sqlite3.OperationalError:
            # Column already exists
            pass

def init_db() -> None:
    """Create all tables referenced by the routes if they do not yet exist.

    Column sets are derived directly from the INSERT/SELECT statements used across
    ``backend/routes/*`` and ``backend/services/pipeline_service.py``.
    """
    with _lock:
        conn = _connect()
        try:
            conn.executescript(_SCHEMA_SQL)
            _migrate_patients_schema(conn)
            conn.commit()
        finally:
            conn.close()


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS patients (
    id TEXT PRIMARY KEY,
    phone TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    name TEXT NOT NULL,
    date_of_birth TEXT,
    gender TEXT,
    blood_group TEXT,
    email TEXT,
    address TEXT,
    emergency_contact TEXT,
    emergency_phone TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS doctors (
    id TEXT PRIMARY KEY,
    phone TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    name TEXT NOT NULL,
    specialization TEXT,
    license_number TEXT,
    email TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS reports (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL,
    filename TEXT,
    filepath TEXT,
    filetype TEXT,
    shared_at TEXT,
    status TEXT DEFAULT 'processing',
    ocr_text TEXT,
    doc_type TEXT,
    ocr_engine TEXT,
    duration REAL,
    error TEXT,
    analyzed INTEGER DEFAULT 0,
    classification TEXT,
    structured_results TEXT,
    analysis TEXT
);

CREATE TABLE IF NOT EXISTS allergies (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL,
    allergen TEXT,
    severity TEXT,
    reaction TEXT,
    noted_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS conditions (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL,
    name TEXT,
    status TEXT,
    diagnosed_at TEXT,
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS medications (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL,
    name TEXT,
    dosage TEXT,
    frequency TEXT,
    status TEXT,
    prescribed_by TEXT,
    start_date TEXT,
    end_date TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS vitals (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL,
    systolic REAL,
    diastolic REAL,
    heart_rate REAL,
    temperature REAL,
    spo2 REAL,
    respiratory_rate REAL,
    weight REAL,
    height REAL,
    blood_sugar REAL,
    notes TEXT,
    recorded_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS prescriptions (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL,
    doctor_name TEXT,
    diagnosis TEXT,
    notes TEXT,
    items TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS clinical_notes (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL,
    doctor_name TEXT,
    visit_type TEXT,
    subjective TEXT,
    objective TEXT,
    assessment TEXT,
    plan TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS appointments (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL,
    doctor_name TEXT,
    scheduled_at TEXT,
    duration_min INTEGER,
    visit_type TEXT,
    status TEXT,
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS lab_results (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL,
    test_name TEXT,
    value TEXT,
    unit TEXT,
    reference_low TEXT,
    reference_high TEXT,
    status TEXT,
    report_id TEXT,
    tested_at TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS diagnosis_codes (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL,
    code TEXT,
    description TEXT,
    diagnosed_at TEXT,
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS referrals (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL,
    from_doctor_name TEXT,
    to_specialty TEXT,
    to_doctor_name TEXT,
    reason TEXT,
    urgency TEXT,
    status TEXT,
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS invoices (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL,
    items TEXT,
    subtotal REAL,
    tax REAL,
    total REAL,
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS insurance (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL,
    provider_name TEXT,
    policy_number TEXT,
    group_number TEXT,
    subscriber_name TEXT,
    relationship TEXT,
    effective_date TEXT,
    expiry_date TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    sender_type TEXT,
    sender_id TEXT,
    receiver_type TEXT,
    receiver_id TEXT,
    subject TEXT,
    body TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS notifications (
    id TEXT PRIMARY KEY,
    user_type TEXT,
    user_id TEXT,
    title TEXT,
    body TEXT,
    kind TEXT DEFAULT 'message',
    read INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS templates (
    id TEXT PRIMARY KEY,
    template_type TEXT,
    name TEXT,
    content TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS providers (
    id TEXT PRIMARY KEY,
    kind TEXT,
    name TEXT,
    engine TEXT,
    config TEXT,
    is_default INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS icd10_codes (
    code TEXT PRIMARY KEY,
    description TEXT,
    category TEXT
);

CREATE TABLE IF NOT EXISTS drug_interactions (
    id TEXT PRIMARY KEY,
    drug_a TEXT,
    drug_b TEXT,
    severity TEXT,
    description TEXT
);

CREATE TABLE IF NOT EXISTS audit_log (
    id TEXT PRIMARY KEY,
    user_type TEXT,
    user_id TEXT,
    action TEXT,
    ref_type TEXT,
    ref_id TEXT,
    details TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
"""


# ── helper functions used by routes / tests ──────────────────────────────────
def _migrate_reports_schema(conn: sqlite3.Connection) -> None:
    """Idempotently add any missing ``reports`` columns used by the pipeline.

    The main schema already declares them in ``init_db()``; this exists so callers
    that only hold a connection (e.g. ``reports_routes.py``) can guarantee the
    columns exist independently of whether ``init_db()`` ran first.
    """
    existing = {r["name"] for r in conn.execute("PRAGMA table_info(reports)")}
    for col, ddl in _REPORT_COLUMNS.items():
        if col not in existing:
            conn.execute(f"ALTER TABLE reports ADD COLUMN {col} {ddl}")
    conn.commit()


_REPORT_COLUMNS = {
    "status": "TEXT DEFAULT 'processing'",
    "ocr_text": "TEXT",
    "doc_type": "TEXT",
    "ocr_engine": "TEXT",
    "duration": "REAL",
    "error": "TEXT",
    "analyzed": "INTEGER DEFAULT 0",
    "classification": "TEXT",
    "structured_results": "TEXT",
    "analysis": "TEXT",
}


def _notify(conn: sqlite3.Connection, user_type: str, user_id: str,
            title: str, body: str, kind: str = "message") -> None:
    """Insert a notification row for a user (patient/doctor/admin)."""
    conn.execute(
        "INSERT INTO notifications (id, user_type, user_id, title, body, kind, created_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (str(uuid.uuid4()), user_type, user_id, title, body, kind,
         datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()


def _audit(conn: sqlite3.Connection, user_type: str, user_id: str, action: str,
           ref_type: str, ref_id: str, details: str) -> None:
    """Append an audit-log entry."""
    conn.execute(
        "INSERT INTO audit_log (id, user_type, user_id, action, ref_type, ref_id, details, created_at) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (str(uuid.uuid4()), user_type, user_id, action, ref_type, ref_id, details,
         datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()


def _get_provider_row(conn: sqlite3.Connection, provider_id: Optional[str],
                      kind: str) -> Optional[sqlite3.Row]:
    """Return the provider row for ``kind`` ('ai' or 'ocr'), preferring the default.

    Mirrors the lookup used in ``reports_routes.py``: if an explicit id is given use
    it, otherwise fall back to the row marked ``is_default`` for that kind.
    """
    if provider_id:
        row = conn.execute(
            "SELECT * FROM providers WHERE id=? AND kind=?", (provider_id, kind)
        ).fetchone()
        return row
    row = conn.execute(
        "SELECT * FROM providers WHERE kind=? AND is_default=1", (kind,)
    ).fetchone()
    if row is None:
        row = conn.execute(
            "SELECT * FROM providers WHERE kind=? ORDER BY created_at DESC LIMIT 1", (kind,)
        ).fetchone()
    return row


# Create the schema eagerly when this module is imported (idempotent). The test
# suite monkeypatches DB_PATH and calls init_db() itself, so guard against a
# missing/locked file only minimally.
try:  # pragma: no cover
    init_db()
except Exception:
    # Let the caller surface a clearer error on first get_db() use.
    pass
