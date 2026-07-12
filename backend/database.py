"""backend/database.py — SQLite helpers + schema (Session 6).

Extracted verbatim from the old ``main.py`` monolith:
  - ``get_db()``                 connection factory (WAL + FK on)
  - ``init_db()``                schema creation + drug/ICD seed data
  - ``_migrate_reports_schema()``additive column migration for ``reports``
  - ``_notify`` / ``_audit``     small insert helpers used by routes
  - ``_get_provider_row``        provider lookup used by the analyze route

The connection is intentionally per-call (the existing ``get_db()`` factory
pattern) so there is no shared-connection state and no circular-import risk.
"""
from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone

from config import settings

DB_PATH = settings.db_path


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS patients (
            id TEXT PRIMARY KEY,
            phone TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            name TEXT DEFAULT '',
            date_of_birth TEXT DEFAULT '',
            gender TEXT DEFAULT '',
            blood_group TEXT DEFAULT '',
            email TEXT DEFAULT '',
            address TEXT DEFAULT '',
            emergency_contact TEXT DEFAULT '',
            emergency_phone TEXT DEFAULT '',
            photo_url TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS doctors (
            id TEXT PRIMARY KEY,
            phone TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            name TEXT NOT NULL,
            specialization TEXT DEFAULT '',
            license_number TEXT DEFAULT '',
            email TEXT DEFAULT '',
            photo_url TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS reports (
            id TEXT PRIMARY KEY,
            patient_id TEXT NOT NULL REFERENCES patients(id),
            filename TEXT NOT NULL,
            filepath TEXT NOT NULL,
            filetype TEXT NOT NULL,
            ocr_text TEXT DEFAULT '',
            analysis TEXT DEFAULT '',
            shared_at TEXT NOT NULL,
            analyzed INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS providers (
            id TEXT PRIMARY KEY,
            kind TEXT NOT NULL,
            name TEXT NOT NULL,
            engine TEXT NOT NULL,
            config TEXT NOT NULL DEFAULT '{}',
            is_default INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS allergies (
            id TEXT PRIMARY KEY,
            patient_id TEXT NOT NULL REFERENCES patients(id),
            allergen TEXT NOT NULL,
            severity TEXT DEFAULT 'mild',
            reaction TEXT DEFAULT '',
            noted_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS conditions (
            id TEXT PRIMARY KEY,
            patient_id TEXT NOT NULL REFERENCES patients(id),
            name TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            diagnosed_at TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS medications (
            id TEXT PRIMARY KEY,
            patient_id TEXT NOT NULL REFERENCES patients(id),
            name TEXT NOT NULL,
            dosage TEXT DEFAULT '',
            frequency TEXT DEFAULT '',
            status TEXT DEFAULT 'active',
            prescribed_by TEXT DEFAULT '',
            start_date TEXT DEFAULT '',
            end_date TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS vitals (
            id TEXT PRIMARY KEY,
            patient_id TEXT NOT NULL REFERENCES patients(id),
            recorded_by TEXT DEFAULT '',
            systolic INTEGER,
            diastolic INTEGER,
            heart_rate INTEGER,
            temperature REAL,
            spo2 INTEGER,
            respiratory_rate INTEGER,
            weight REAL,
            height REAL,
            blood_sugar REAL,
            notes TEXT DEFAULT '',
            recorded_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS prescriptions (
            id TEXT PRIMARY KEY,
            patient_id TEXT NOT NULL REFERENCES patients(id),
            doctor_id TEXT DEFAULT '',
            doctor_name TEXT DEFAULT '',
            diagnosis TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            items TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS clinical_notes (
            id TEXT PRIMARY KEY,
            patient_id TEXT NOT NULL REFERENCES patients(id),
            doctor_id TEXT DEFAULT '',
            doctor_name TEXT DEFAULT '',
            visit_type TEXT DEFAULT 'follow-up',
            subjective TEXT DEFAULT '',
            objective TEXT DEFAULT '',
            assessment TEXT DEFAULT '',
            plan TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS appointments (
            id TEXT PRIMARY KEY,
            patient_id TEXT NOT NULL REFERENCES patients(id),
            doctor_id TEXT DEFAULT '',
            doctor_name TEXT DEFAULT '',
            scheduled_at TEXT NOT NULL,
            duration_min INTEGER DEFAULT 30,
            visit_type TEXT DEFAULT 'consultation',
            status TEXT DEFAULT 'scheduled',
            notes TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS lab_results (
            id TEXT PRIMARY KEY,
            patient_id TEXT NOT NULL REFERENCES patients(id),
            test_name TEXT NOT NULL,
            value REAL,
            unit TEXT DEFAULT '',
            reference_low REAL,
            reference_high REAL,
            status TEXT DEFAULT 'normal',
            report_id TEXT DEFAULT '',
            tested_at TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            sender_type TEXT NOT NULL,
            sender_id TEXT NOT NULL,
            receiver_type TEXT NOT NULL,
            receiver_id TEXT NOT NULL,
            subject TEXT DEFAULT '',
            body TEXT NOT NULL,
            is_read INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id TEXT PRIMARY KEY,
            actor_type TEXT NOT NULL,
            actor_id TEXT NOT NULL,
            action TEXT NOT NULL,
            resource_type TEXT DEFAULT '',
            resource_id TEXT DEFAULT '',
            details TEXT DEFAULT '',
            ip_address TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS notifications (
            id TEXT PRIMARY KEY,
            user_type TEXT NOT NULL,
            user_id TEXT NOT NULL,
            title TEXT NOT NULL,
            body TEXT DEFAULT '',
            category TEXT DEFAULT 'info',
            is_read INTEGER DEFAULT 0,
            link TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS icd10_codes (
            code TEXT PRIMARY KEY,
            description TEXT NOT NULL,
            category TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS diagnosis_codes (
            id TEXT PRIMARY KEY,
            patient_id TEXT NOT NULL REFERENCES patients(id),
            code TEXT NOT NULL,
            description TEXT NOT NULL,
            diagnosed_at TEXT NOT NULL,
            notes TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS drug_interactions (
            id TEXT PRIMARY KEY,
            drug_a TEXT NOT NULL,
            drug_b TEXT NOT NULL,
            severity TEXT NOT NULL,
            description TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS referrals (
            id TEXT PRIMARY KEY,
            patient_id TEXT NOT NULL REFERENCES patients(id),
            from_doctor_id TEXT DEFAULT '',
            from_doctor_name TEXT DEFAULT '',
            to_specialty TEXT NOT NULL,
            to_doctor_name TEXT DEFAULT '',
            reason TEXT NOT NULL,
            urgency TEXT DEFAULT 'routine',
            status TEXT DEFAULT 'pending',
            notes TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS templates (
            id TEXT PRIMARY KEY,
            doctor_id TEXT DEFAULT '',
            template_type TEXT NOT NULL,
            name TEXT NOT NULL,
            content TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS invoices (
            id TEXT PRIMARY KEY,
            patient_id TEXT NOT NULL REFERENCES patients(id),
            doctor_id TEXT DEFAULT '',
            items TEXT NOT NULL DEFAULT '[]',
            subtotal REAL DEFAULT 0,
            tax REAL DEFAULT 0,
            total REAL DEFAULT 0,
            status TEXT DEFAULT 'draft',
            notes TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS insurance (
            id TEXT PRIMARY KEY,
            patient_id TEXT NOT NULL REFERENCES patients(id),
            provider_name TEXT NOT NULL,
            policy_number TEXT NOT NULL,
            group_number TEXT DEFAULT '',
            subscriber_name TEXT DEFAULT '',
            relationship TEXT DEFAULT 'self',
            effective_date TEXT DEFAULT '',
            expiry_date TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );
    """)

    # Seed common drug interactions
    interactions = [
        ("Warfarin", "Aspirin", "major", "Increased risk of bleeding"),
        ("Warfarin", "Ibuprofen", "major", "Increased risk of GI bleeding and anticoagulant effect"),
        ("Metformin", "Alcohol", "major", "Risk of lactic acidosis"),
        ("ACE Inhibitors", "Potassium", "major", "Risk of hyperkalemia"),
        ("SSRIs", "MAOIs", "contraindicated", "Risk of serotonin syndrome — potentially fatal"),
        ("Statins", "Grapefruit", "moderate", "Increased statin levels, risk of rhabdomyolysis"),
        ("Methotrexate", "NSAIDs", "major", "Decreased renal clearance of methotrexate"),
        ("Digoxin", "Amiodarone", "major", "Increased digoxin levels, risk of toxicity"),
        ("Ciprofloxacin", "Theophylline", "major", "Increased theophylline levels, risk of seizures"),
        ("Lithium", "NSAIDs", "major", "Increased lithium levels, risk of toxicity"),
        ("Clopidogrel", "Omeprazole", "moderate", "Reduced antiplatelet effect of clopidogrel"),
        ("Sildenafil", "Nitrates", "contraindicated", "Severe hypotension"),
        ("Fluconazole", "Warfarin", "major", "Increased warfarin effect, risk of bleeding"),
        ("Erythromycin", "Statins", "major", "Increased statin levels, risk of rhabdomyolysis"),
        ("Insulin", "Beta Blockers", "moderate", "Masked hypoglycemia symptoms"),
        ("Metronidazole", "Alcohol", "major", "Disulfiram-like reaction — nausea, vomiting, flushing"),
        ("Tetracycline", "Antacids", "moderate", "Reduced tetracycline absorption"),
        ("Phenytoin", "Valproic Acid", "major", "Altered levels of both drugs"),
        ("Tramadol", "SSRIs", "major", "Risk of serotonin syndrome and seizures"),
        ("Benzodiazepines", "Opioids", "major", "Risk of respiratory depression and death"),
    ]
    for a, b, sev, desc in interactions:
        conn.execute(
            "INSERT OR IGNORE INTO drug_interactions (id, drug_a, drug_b, severity, description) VALUES (?,?,?,?,?)",
            (f"di_{a.lower().replace(' ','_')}_{b.lower().replace(' ','_')}", a, b, sev, desc),
        )

    # Seed common ICD-10 codes
    icd_codes = [
        ("E11", "Type 2 diabetes mellitus", "Endocrine"),
        ("I10", "Essential hypertension", "Circulatory"),
        ("J06.9", "Acute upper respiratory infection, unspecified", "Respiratory"),
        ("M54.5", "Low back pain", "Musculoskeletal"),
        ("K21.0", "Gastro-esophageal reflux with esophagitis", "Digestive"),
        ("F32.9", "Major depressive disorder, single episode, unspecified", "Mental"),
        ("J45.909", "Unspecified asthma, uncomplicated", "Respiratory"),
        ("E78.5", "Hyperlipidemia, unspecified", "Endocrine"),
        ("N39.0", "Urinary tract infection, site not specified", "Genitourinary"),
        ("R51", "Headache", "Symptoms"),
        ("J20.9", "Acute bronchitis, unspecified", "Respiratory"),
        ("R10.9", "Unspecified abdominal pain", "Symptoms"),
        ("E03.9", "Hypothyroidism, unspecified", "Endocrine"),
        ("G43.909", "Migraine, unspecified, not intractable", "Nervous"),
        ("L30.9", "Dermatitis, unspecified", "Skin"),
        ("R05", "Cough", "Symptoms"),
        ("K58.9", "Irritable bowel syndrome without diarrhea", "Digestive"),
        ("M79.3", "Panniculitis, unspecified", "Musculoskeletal"),
        ("R11.2", "Nausea with vomiting, unspecified", "Symptoms"),
        ("D64.9", "Anemia, unspecified", "Blood"),
        ("I25.10", "Atherosclerotic heart disease", "Circulatory"),
        ("J18.9", "Pneumonia, unspecified organism", "Respiratory"),
        ("E55.9", "Vitamin D deficiency, unspecified", "Endocrine"),
        ("B34.9", "Viral infection, unspecified", "Infectious"),
        ("R50.9", "Fever, unspecified", "Symptoms"),
    ]
    for code, desc, cat in icd_codes:
        conn.execute(
            "INSERT OR IGNORE INTO icd10_codes (code, description, category) VALUES (?,?,?)",
            (code, desc, cat),
        )

    conn.commit()
    conn.close()


def _migrate_reports_schema(conn: sqlite3.Connection):
    """Add auto-processing / timing columns to `reports` if missing."""
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(reports)")}
    needed = {
        "doc_type": "TEXT DEFAULT ''",
        "ocr_engine": "TEXT DEFAULT ''",
        "ocr_started_at": "TEXT DEFAULT ''",
        "ocr_completed_at": "TEXT DEFAULT ''",
        "processing_duration_ms": "INTEGER DEFAULT 0",
        "status": "TEXT DEFAULT 'pending'",
        "structured_results": "TEXT DEFAULT '[]'",
        "error": "TEXT DEFAULT ''",
    }
    for name, typ in needed.items():
        if name not in cols:
            conn.execute(f"ALTER TABLE reports ADD COLUMN {name} {typ}")
    conn.commit()


def _notify(conn, user_type: str, user_id: str, title: str, body: str = "", category: str = "info", link: str = ""):
    nid = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO notifications (id, user_type, user_id, title, body, category, link, created_at) VALUES (?,?,?,?,?,?,?,?)",
        (nid, user_type, user_id, title, body, category, link, now),
    )


def _audit(conn, actor_type: str, actor_id: str, action: str, resource_type: str = "", resource_id: str = "", details: str = ""):
    aid = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO audit_log (id, actor_type, actor_id, action, resource_type, resource_id, details, created_at) VALUES (?,?,?,?,?,?,?,?)",
        (aid, actor_type, actor_id, action, resource_type, resource_id, details, now),
    )


def _get_provider_row(conn: sqlite3.Connection, provider_id: str, kind: str) -> dict:
    if provider_id:
        row = conn.execute("SELECT * FROM providers WHERE id=? AND kind=?", (provider_id, kind)).fetchone()
        if row:
            return dict(row)
    row = conn.execute("SELECT * FROM providers WHERE kind=? AND is_default=1", (kind,)).fetchone()
    if row:
        return dict(row)
    return {}
