# PLAN — No-Login Test Version (2 Cards Work Without Auth)

## SECTION A — GOAL DEFINITION

### 1. What is being built or changed?
The landing page shows **2 cards** (Patient Portal + Doctor Portal). Previously the
Patient Portal tried to auto-login against `/api/patient/login` using a default
account (`5511999` / `password`). Because the login/register code path was
partially removed (or the default patient was never seeded), the backend returns
**401 / `UNAUTHENTICATED`**, which surfaces as the error the user is seeing.

For this **test-only version** we want:
- No login screen, no register screen, no token handling in the UI.
- The 2 cards on the landing page both work directly.
- Patient Portal: upload + list reports **without any auth token**.
- Doctor Portal: already works without login (lists all patients from the open DB).

### 2. What does "done" look like?
- Opening the app shows the 2-card landing page.
- Clicking **Patient Portal** immediately shows the uploader + report list — no
  spinner, no "Authenticating…", no "Authentication Failed" state.
- Uploading a file works and the report appears in the list.
- Clicking **Doctor Portal** lists patients and runs the pipeline as before.
- No `UNAUTHENTICATED` / 401 errors in the backend log for patient flows.
- No dead login/register UI code remains in `PatientPortal.tsx`.

### 3. What is explicitly out of scope?
- Removing backend auth endpoints entirely (they're harmless; just unused by the UI).
- Doctor-side changes (already login-free).
- Pipeline / OCR / AI provider logic.

---

## SECTION B — ROOT CAUSE

`PatientPortal.tsx` `useEffect` calls `api.login(defaultPhone, defaultPassword)`.
If the default patient row doesn't exist (DB was reset, or register also fails),
`setToken` is never called and the component renders the **"Authentication Failed"**
fallback. Even when login "works", every subsequent call
(`uploadReport`, `patientReports`) depends on a valid token. The backend
`/api/patient/upload` and `/api/patient/reports` endpoints require `decode_token`,
so any token issue → 401.

The cleanest fix for a **test-only** build is to bypass auth entirely on the
patient-facing upload/reports endpoints and remove all token logic from the UI.

---

## SECTION C — CHANGES

### 1. Backend — seed a default patient + add no-auth endpoints
**File:** `backend/main.py` (lifespan) and `backend/routes/reports_routes.py`

- In `lifespan`, after `init_db()`, seed a default patient row
  (`phone='5511999'`, name `'Test Patient'`) if it doesn't exist, and expose its
  `patient_id` via a module constant `DEFAULT_PATIENT_ID`.
- Add **no-auth** endpoints alongside the existing ones (keep old ones for
  compatibility):
  - `POST /api/test/upload`           — upload for the default patient (no token)
  - `GET  /api/test/reports`           — list reports for the default patient
  - `GET  /api/test/file/{report_id}` — serve file (reuse existing `/api/file/{id}`)
- These endpoints use `DEFAULT_PATIENT_ID` directly, no `decode_token`.

### 2. Frontend — `api.ts`
**File:** `frontend/src/api.ts`

- Add `testUploadReport(file)` and `testReports()` that hit the new `/api/test/*`
  endpoints (no token parameter).
- Keep `fileUrl` as-is (uses `/api/file/{id}` which is already public).

### 3. Frontend — `PatientPortal.tsx`
**File:** `frontend/src/pages/PatientPortal.tsx`

- Remove: `Screen` type, `screen`/`isRegister`/`phone`/`password`/`name`/`token`
  state, the entire `autoLogin` `useEffect`, and the `!token` fallback block.
- Replace `loadReports(token)` with `loadReports()` using `api.testReports()`.
- Replace `api.uploadReport(token, file)` with `api.testUploadReport(file)`.
- Component renders the dashboard directly on mount.

### 4. Landing page — `RolePicker.tsx`
No changes needed — the 2 cards already call `onPick("patient")` / `onPick("doctor")`.

---

## SECTION D — PROGRESS CHECKLIST

- [ ] 1. Backend: seed default patient in `lifespan`
- [ ] 2. Backend: add `/api/test/upload` + `/api/test/reports` no-auth endpoints
- [ ] 3. Frontend `api.ts`: add `testUploadReport` + `testReports`
- [ ] 4. Frontend `PatientPortal.tsx`: remove all login/token code
- [ ] 5. Build frontend + start backend, verify no 401 errors
