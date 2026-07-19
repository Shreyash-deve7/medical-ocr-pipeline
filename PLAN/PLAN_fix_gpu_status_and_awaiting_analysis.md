# PLAN — Fix Backend "Not Found" Root, CUDA Status Display, and "Awaiting Analysis" UX

## SECTION A — GOAL DEFINITION

1. **What is being built or changed?**
   Three distinct issues are being addressed:
   - **Issue 1 (Cosmetic — Root Route)**: `localhost:3000` shows `{"detail":"Not Found"}`. A root `/` route needs to be added to avoid confusing developers/testers.
   - **Issue 2 (Informational — CUDA/Qwen)**: The GPU status panel shows "CUDA Not Available" and "Qwen2.5-VL: Idle". These reflect the actual state of the machine (PyTorch CPU-only build, Qwen not loaded because `QWEN_VL_SERVER_URL` is set so it's intentionally skipped). The display needs to clearly communicate to the user that these are expected/intentional states, not errors.
   - **Issue 3 (UX Bug — "Awaiting Analysis")**: On the **Patient Portal** (`My Reports` page), all 5 uploaded files show "Awaiting Analysis" as a status badge. This status badge currently shows on every report that has `analyzed=0` (false). The user wants: reports should show status **"Uploaded"** (neutral) on the list page. The "Awaiting Analysis" / pipeline states should only appear on the **Doctor Portal** side after the user clicks "Run Pipeline" (which is already correctly implemented there). The patient sees their report was uploaded and the doctor analyzes it.

2. **What does "done" look like?**
   - `localhost:3000` returns a helpful JSON response (e.g., API info / redirect hint).
   - The GPU Status panel clearly labels Qwen as "Using microservice (external)" instead of "Idle" when `QWEN_VL_SERVER_URL` is set, and CUDA shows "CPU mode" as a neutral notice, not a red failure.
   - The Patient Portal report list shows "Uploaded" as the status badge for reports not yet analyzed. "Awaiting Analysis" badge is removed from the patient view entirely. The Doctor Portal is unchanged.

3. **What is explicitly out of scope?**
   - Installing CUDA / PyTorch GPU build.
   - Actually loading the Qwen model in-process (it is deliberately offloaded to the microservice).
   - Changing the Doctor Portal report list (which correctly shows "Pending" for unanalyzed reports and has the "Run Pipeline" workflow).

---

## SECTION B — TECH STACK

- **Backend**: Python, FastAPI (`backend/main.py`, `backend/gpu_manager.py`, `backend/routes/admin_routes.py` for the GPU status endpoint)
- **Frontend**: React + TypeScript (`frontend/src/pages/PatientPortal.tsx`, `frontend/src/components/GpuStatusPanel.tsx`)
- **No new dependencies** needed.

---

## SECTION C — SESSION MODULARIZATION

### Session 1: Fix Root Route on `localhost:3000`

- **Objective**: Add a `GET /` route to FastAPI that returns a helpful API info message instead of `{"detail":"Not Found"}`.
- **Scope**: `backend/main.py` — add a root endpoint.
- **Output**: Hitting `http://localhost:3000/` returns `{"name": "MedVault API", "version": "1.0", "docs": "/docs", "status": "ok"}` or similar.
- **Connects to**: Nothing downstream depends on this.
- **Failure Surface**: None — trivially simple additive change.

### Session 2: Fix GPU Status Panel — CUDA & Qwen Display

- **Objective**: Update the `gpu_manager.py` status to return additional metadata about whether Qwen is running as an external microservice. Update the `GpuStatusPanel.tsx` component to display:
  - CUDA "Not Available" → neutral **"CPU mode"** (blue/gray, not red/error) with explanation tooltip.
  - Qwen "Idle" when `QWEN_VL_SERVER_URL` is configured → **"External microservice"** badge (green/blue), not "Idle".
- **Scope**: `backend/gpu_manager.py`, `backend/routes/admin_routes.py` (GPU status endpoint), `frontend/src/components/GpuStatusPanel.tsx`.
- **Output**: Status panel correctly communicates CPU mode and external Qwen microservice without alarming red indicators.
- **Connects to**: Session 3 is independent.
- **Failure Surface**: If `QWEN_VL_SERVER_URL` env var is not set in the process where the backend runs, Qwen will still show "Idle". We will document this in the panel.

### Session 3: Fix "Awaiting Analysis" on Patient Portal → Change to "Uploaded"

- **Objective**: On the Patient Portal (`PatientPortal.tsx`), change the status badge logic so:
  - Reports with `analyzed=0` → show **"Uploaded"** (neutral badge, e.g. gray/blue) instead of "Awaiting Analysis".
  - Reports with `analyzed=1` → keep showing **"Analyzed"** (green badge).
  - Remove the pulsing "dot" animation from the patient side (it's alarming for a non-technical patient).
- **Scope**: `frontend/src/pages/PatientPortal.tsx` (line ~145), `frontend/src/styles.css` if needed.
- **Output**: Patient report list shows "Uploaded" for unanalyzed reports. Doctor Portal is untouched.
- **Connects to**: Nothing downstream depends on this.
- **Failure Surface**: CSS class name conflicts. We will reuse existing `.tag` class pattern.

---

## SECTION D — PROGRESS CHECKLIST

- [ ] Session 1: Fix Root Route (`localhost:3000/`)
  - [ ] Add `GET /` endpoint to `backend/main.py` returning API info JSON
  - [ ] Verify: hitting `localhost:3000/` returns a helpful JSON object (not 404)
  - [ ] Verify: `localhost:3000/docs` still works (FastAPI Swagger UI)

- [ ] Session 2: Fix GPU Status Panel — CUDA & Qwen Display
  - [ ] Update `backend/gpu_manager.py` `GPUStatus` dataclass to include `qwen_using_microservice: bool`
  - [ ] Update `gpu_status()` function to set `qwen_using_microservice = bool(os.environ.get("QWEN_VL_SERVER_URL"))`
  - [ ] Update `frontend/src/components/GpuStatusPanel.tsx` to render "CPU mode" (neutral) instead of red "Not available" for CUDA
  - [ ] Update `GpuStatusPanel.tsx` to render "External microservice" (green) for Qwen when `qwen_using_microservice` is true
  - [ ] Verify: GPU status panel shows correct states without alarming colors when in CPU / microservice mode

- [ ] Session 3: Fix "Awaiting Analysis" → "Uploaded" on Patient Portal
  - [ ] Edit `frontend/src/pages/PatientPortal.tsx` line 145: change `<span className="tag pending pulse">⏳ Awaiting Analysis</span>` to `<span className="tag uploaded">Uploaded</span>`
  - [ ] Add `.tag.uploaded` CSS style in `frontend/src/styles.css` (neutral blue/gray)
  - [ ] Verify: Reports list on Patient Portal shows "Uploaded" for unanalyzed reports
  - [ ] Verify: Doctor Portal report list is unchanged (still shows "Pending" + "Run Pipeline" button)
