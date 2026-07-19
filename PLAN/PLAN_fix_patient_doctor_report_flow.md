# PLAN — Fix Patient→Doctor Report Visibility

## SECTION A — GOAL DEFINITION

1. **What is being built or changed?**
   The data flow between the Patient Portal (upload) and the Doctor Portal (analyze) is broken. Uploaded reports do not appear on the Doctor's dashboard for analysis.

2. **What does "done" look like?**
   - When a patient uploads a report via the Patient Portal, the doctor can immediately see it in the Doctor Portal under the correct patient row.
   - The doctor can click the patient → see the uploaded report → click "Run Pipeline" → run OCR + analysis.
   - The doctor patient list shows the correct `report_count`.

3. **What is explicitly out of scope?**
   - Authentication / login flow changes.
   - Changing the OCR pipeline itself.
   - The SQLite `date_of_birth` column error (separate migration bug, tracked separately).

---

## SECTION B — ROOT CAUSE ANALYSIS

### The Core Bug (Two-Part)

**Part 1 — "Default Test Patient" is invisible to the Doctor Portal query**

- The Patient Portal uploads via `/api/test/upload` — no login required.  
- These uploads are stored under `DEFAULT_PATIENT_ID`, the seeded test patient with `phone = "0000000000"`.
- The Doctor Portal calls `GET /api/doctor/patients` which queries `SELECT * FROM patients … ORDER BY created_at DESC`.
- **The default test patient IS in the patients table**, so it SHOULD appear. The issue is Part 2.

**Part 2 — Doctor's `list_patients` query fails with `no such column: p.date_of_birth`**

Looking at `doctor_routes.py` line 24:
```sql
SELECT p.id, p.phone, p.name, p.date_of_birth, p.gender, p.blood_group, p.created_at, COUNT(r.id) as report_count
FROM patients p LEFT JOIN reports r ON p.id = r.patient_id
GROUP BY p.id ORDER BY p.created_at DESC
```

But in `database.py`, the `patients` table schema is:
```sql
CREATE TABLE IF NOT EXISTS patients (
    id TEXT, phone TEXT, password_hash TEXT, name TEXT, created_at TEXT
)
```

**`date_of_birth`, `gender`, and `blood_group` do NOT exist in the schema** — the doctor route queries columns that were never created. This causes the SQLite error we already saw in the server crash log: `sqlite3.OperationalError: no such column: p.date_of_birth`. The `GET /api/doctor/patients` endpoint is completely broken, so the patient list never loads in the Doctor Portal → reports are never visible.

**Fix Options:**
- **Option A (Chosen):** Add the missing columns (`date_of_birth`, `gender`, `blood_group`) to the `patients` table schema in `database.py` AND add a migration to `init_db()` to `ALTER TABLE` the existing DB if columns are missing.
- Option B: Remove those columns from the query in `doctor_routes.py`. Simpler but loses useful data.

We go with **Option A** — the columns are referenced in multiple routes (`/api/patient/profile` PUT, etc.) so they clearly were intended to exist.

---

## SECTION B — TECH STACK

- **Backend**: Python, SQLite, FastAPI
  - `backend/database.py` — schema & migration
  - `backend/routes/doctor_routes.py` — fix query if needed
- **No frontend changes needed** (the frontend is correct; the backend just needs to stop throwing 500)

---

## SECTION C — SESSION MODULARIZATION

### Session 1: Fix Database Schema — Add Missing Patient Columns

- **Objective**: Add `date_of_birth TEXT`, `gender TEXT`, `blood_group TEXT`, `email TEXT`, `address TEXT`, `emergency_contact TEXT`, `emergency_phone TEXT` to the `patients` table definition and add an `ALTER TABLE` migration that safely adds them to the existing DB at startup.
- **Scope**: `backend/database.py` — `_SCHEMA_SQL` (CREATE TABLE definition) + `init_db()` or a new `_migrate_patients_schema()` helper called from `init_db()`.
- **Output**: Server starts without any `no such column` error. The patients table has all the columns that the routes expect.
- **Connects to**: Session 2 immediately benefits — once the endpoint works, the Doctor Portal can list patients and their reports.
- **Failure Surface**: SQLite `ALTER TABLE` only supports adding one column at a time — need separate `ALTER TABLE ADD COLUMN` per missing column. We use a `try/except` per column to handle the case where the column was already added.

### Session 2: Verify End-to-End Flow in Doctor Portal

- **Objective**: Confirm that after the schema fix, the Doctor Portal correctly lists:
  1. The default test patient (with phone `0000000000`) and their `report_count`.
  2. That clicking the patient shows the uploaded reports.
  3. That "Run Pipeline" triggers OCR and analysis.
- **Scope**: No code changes — verification only. Hit the live API at `localhost:3000/api/doctor/patients` to confirm the response is a valid JSON list.
- **Output**: `GET /api/doctor/patients` returns a non-empty JSON array including the default test patient with a correct `report_count`.
- **Connects to**: Nothing — this is the final verification step.
- **Failure Surface**: If the existing SQLite DB file (`medvault.db`) has a lock or is corrupted, the migration may fail. The fix is to delete the DB file and let `init_db()` recreate it fresh.

---

## SECTION D — PROGRESS CHECKLIST

- [ ] Session 1: Fix Database Schema
  - [ ] Add all missing columns to `_SCHEMA_SQL` `CREATE TABLE IF NOT EXISTS patients` block
  - [ ] Add `_migrate_patients_schema(conn)` helper function using `ALTER TABLE … ADD COLUMN IF NOT EXISTS` (or try/except per column)
  - [ ] Call `_migrate_patients_schema` from `init_db()` after the schema creation
  - [ ] Restart server — confirm zero `no such column` errors in the log
- [ ] Session 2: Verify End-to-End Flow
  - [ ] `GET localhost:3000/api/doctor/patients` returns valid JSON list
  - [ ] Default test patient appears with correct `report_count`
  - [ ] Doctor Portal UI shows patient and reports list
  - [ ] "Run Pipeline" button is functional on a report
