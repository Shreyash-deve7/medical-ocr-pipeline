# PLAN: Stuck Upload and Inactive GPU Status Fixes

This plan outlines the diagnosis and step-by-step resolution for the issues where:
1. The image upload gets stuck at 92% and fails with "failed to fetch".
2. The GPU status shows "Internal Server Error" (inactive).

---

## SECTION A — GOAL DEFINITION

### 1. What is being built or changed?
- Diagnosing and clearing zombie process port locks (ports `5173` and `8000`) on Windows.
- Updating Vite's proxy target configuration to bypass Node.js IPv6 resolution conflicts.
- Automating clean start workflows.

### 2. What does "done" look like?
- The backend uvicorn server successfully binds to port `8000`.
- The frontend Vite dev server successfully binds to port `5173`.
- Uploading an image to `http://localhost:5173` successfully routes to the backend, triggers OCR, and finishes processing.
- The GPU Status panel shows active status and loads successfully.

### 3. Out of Scope
- Modifying OCR routing or model inference logic.
- Training classifiers or editing extraction schemas.

---

## SECTION B — TECH STACK
- PowerShell / Windows Command Line
- Node.js (Vite)
- Python (FastAPI / Uvicorn)

---

## SECTION C — SESSION MODULARIZATION

### Session 1: Terminate Zombie Processes
- **Objective:** Clear any stale Node.js or Python processes holding port `5173` and `8000`.
- **Scope:** PowerShell environment, Windows Process Manager.
- **Output:** Ports `5173` and `8000` are completely free.
- **Connects to:** Session 2 (avoids port collisions when launching).
- **Failure Surface:** Access denied when trying to kill processes (requires running shell as Administrator).

### Session 2: Resolve Localhost Proxy Mismatch
- **Objective:** Update Vite configuration to point directly to the IPv4 address (`127.0.0.1`) instead of `localhost`.
- **Scope:** [vite.config.ts](file:///c:/Users/oliad/Desktop/intern-ocr-paddleocr-aditya/pipeline_v1/frontend/vite.config.ts)
- **Output:** Vite proxy points explicitly to IPv4, avoiding `ECONNREFUSED` from Node trying to resolve to IPv6 loopback `[::1]`.
- **Connects to:** Session 3.
- **Failure Surface:** Typo in configuration breaking Vite boot.

### Session 3: Clean Start & Verification
- **Objective:** Launch both servers cleanly and verify connection.
- **Scope:** App startup scripts and browser verification.
- **Output:** Clean console logs showing both ports successfully bound, and successful uploads.

---

## SECTION D — PROGRESS CHECKLIST

- [ ] Session 1: Terminate Zombie Processes
  - [ ] Run PowerShell commands to identify process IDs on ports 5173 and 8000.
  - [ ] Terminate matching processes using `Stop-Process`.
  - [ ] Verify both ports are free.
- [ ] Session 2: Resolve Localhost Proxy Mismatch
  - [ ] Edit `frontend/vite.config.ts` target from `http://localhost:8000` to `http://127.0.0.1:8000`.
- [ ] Session 3: Clean Start & Verification
  - [ ] Run `.venv\Scripts\uvicorn.exe backend.main:app --host 0.0.0.0 --port 8000 --reload` in Terminal 1.
  - [ ] Run `npx vite --port 5173` in Terminal 2 (from `frontend/`).
  - [ ] Verify Vite starts on port `5173` (not `5174`).
  - [ ] Test the page in browser at `http://localhost:5173`.
  - [ ] Verify upload works and GPU status is fetched.
