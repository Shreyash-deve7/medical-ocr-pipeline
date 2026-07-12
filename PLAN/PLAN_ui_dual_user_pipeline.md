# MedVault UI — Dual-User Pipeline-First Redesign
> **Codebase**: `pipeline_v1` | **Goal**: Rebuild PatientPortal, DoctorPortal, and RolePicker to match the updated 8-agent pipeline architecture.

---

## Section A — Goal Definition

### What Is Being Built or Changed?
The current frontend has PatientPortal and DoctorPortal pages that are functional but disconnected from the completed 8-agent pipeline (Sessions 1–8). Specifically:
- The Doctor's "Analyze" button calls the old `/api/doctor/analyze` (regex heuristics), **not** the new `/api/pipeline/run` endpoint (full agentic DAG).
- The Patient dashboard shows only filename + "Pending" tag — no meaningful feedback after upload.
- The RolePicker landing page has 9 cards for features irrelevant to the core demo (Genomics, Telemedicine, etc.), obscuring the primary user journeys.

### What Does "Done" Look Like?
- **Patient** logs in → sees a beautiful upload zone → drags lab report image → sees it in their report list with a live status badge ("Pending" / "Analyzed").
- **Doctor** enters (no login required, current behaviour) → sees patient list → selects patient → sees their reports → clicks **Run Pipeline** on any report → the frontend calls `POST /api/pipeline/run` with the file → shows a 4-panel result card: Classification + OCR text + Extracted lab table + Diagnosis summary.
- The lab results table has **colour-coded flag cells** (CRITICAL_HIGH=red, HIGH=orange, LOW=yellow, NORMAL=green).
- The RolePicker shows exactly **2 hero role cards**: Patient | Doctor.

### What Is Explicitly Out of Scope?
- Doctor authentication/JWT (currently unauthenticated GET — preserved).
- Backend changes of any kind.
- Other pages (PatientChart, OCRWorkbench, Genomics, etc.) — untouched.
- Mobile/responsive redesign beyond what the existing CSS already supports.

---

## Section B — Tech Stack

| Layer | Technology | Notes |
|---|---|---|
| Frontend | React + TypeScript | Existing stack, no framework change |
| Styling | Vanilla CSS (`styles.css`) | Extend existing design system |
| API Client | Fetch-based `api.ts` | Add `runPipeline()` function + TypeScript types |
| New Endpoint | `POST /api/pipeline/run` | Multipart file upload — already exists in backend (Session 8) |
| File Re-fetch | `GET /api/file/{id}` | Fetch existing report as Blob, then POST to pipeline |

**ASSUMPTION:** `/api/pipeline/run` is accessible at `http://localhost:8000/api/pipeline/run` via Vite proxy. The existing Vite config already proxies `/api` to the backend.

---

## Section C — Session Modularisation

### Session UI-1: API Client + TypeScript Types
**Objective:** Add the new `runPipeline()` API function and TypeScript interfaces that all other sessions depend on.

**Scope:**
- `frontend/src/api.ts` — add `runPipeline()`, `PipelineResult` interface, `LabResult` interface

**Output:** Exported function + types; TypeScript compilation passes.

**Connects To:** Sessions UI-3 and UI-4 import from api.ts. If `runPipeline()` has wrong signature, DoctorPortal won't type-check.

**Failure Surface:**
- `/api/pipeline/run` multipart field name mismatch (backend expects `file` — confirmed in `pipeline_routes.py`).
- `PipelineResult` shape mismatch if backend returns unexpected structure — handle with `any` fallback where needed.

---

### Session UI-2: RolePicker Redesign
**Objective:** Replace the 9-card grid with a focused 2-card hero landing (Patient | Doctor).

**Scope:**
- `frontend/src/pages/RolePicker.tsx` — full JSX rewrite of content (Props interface + export signature unchanged)
- `frontend/src/styles.css` — add `.role-hero-card`, `.role-hero-grid` styles with glassmorphism, hover lift

**Output:** A landing page with exactly 2 clickable cards navigating to `"patient"` and `"doctor"` views.

**Connects To:** `App.tsx` — `navigate("patient")` and `navigate("doctor")` calls must be preserved (they already exist).

**Failure Surface:**
- Over-scoping: keep all existing `onPick()` calls for other views accessible via the topbar (not removed, just deprioritised).

---

### Session UI-3: PatientPortal Visual Upgrade
**Objective:** Upgrade the patient dashboard upload experience and report list.

**Scope:**
- `frontend/src/pages/PatientPortal.tsx` — upgrade JSX layout only; all handler logic unchanged
- `frontend/src/styles.css` — add `.upload-zone-hero`, `.status-badge-pending`, `.status-badge-analyzed`

**Output:** Patient sees full-width upload zone with animated border, live progress bar (0% → 100%), and status-aware report cards.

**Connects To:** No logic changes; `handleUpload`, `loadReports`, `onDrop` are identical.

**Failure Surface:**
- Progress bar animation is CSS-only (no real progress events from `fetch` FormData) — will animate to 100% on success, reset on error.

---

### Session UI-4: DoctorPortal Pipeline Integration ← Core Session
**Objective:** Wire the Doctor's "Run Pipeline" button to `/api/pipeline/run` and display the 4-panel result.

**Scope:**
- `frontend/src/pages/DoctorPortal.tsx` — add state + handler + result panel JSX
- `frontend/src/api.ts` — import `runPipeline`, `PipelineResult` (from Session UI-1)

**New State:**
```
pipelineResult: PipelineResult | null
runningPipelineFor: string | null   // report ID
pipelineReportId: string | null     // which report the accordion shows
```

**New Handler `handleRunPipeline(reportId, filename)`:**
1. `setRunningPipelineFor(reportId)`
2. `fetch(api.fileUrl(reportId))` → `.blob()`
3. `api.runPipeline(blob, filename, { summary: true })`
4. `setPipelineResult(result)`, `setPipelineReportId(reportId)`
5. `setRunningPipelineFor(null)`

**New JSX — Pipeline Progress Strip:**
```
[🔄 Preprocess] → [🏷️ Classify] → [📝 OCR] → [🧬 Extract+Diagnose]
```
Each step lights up green once the response arrives.

**New JSX — 4-Panel Accordion:**
- Panel 1: Classification (chip + confidence bar + transforms)
- Panel 2: OCR text (`<pre>` + copy button)
- Panel 3: Lab results table (flag colour coding)
- Panel 4: Diagnosis (summary + patterns + urgent flags + follow-up)

**Output:** Doctor can run the full pipeline and see structured results inline.

**Connects To:** Session UI-1 (`runPipeline`, `PipelineResult`), Session UI-5 (CSS classes for panels/flags).

**Failure Surface:**
- File blob fetch fails (401, 404) → show error toast, reset state.
- Pipeline returns `lab_report: null` (extraction failed) → show graceful empty state in Panel 3.
- `metadata.errors` non-empty → show warning banner above accordion.

---

### Session UI-5: CSS Polish
**Objective:** Add all new CSS utility classes needed by Sessions UI-2–4.

**Scope:**
- `frontend/src/styles.css` — append new rule blocks only (no existing rules modified)

**New Classes:**
| Class | Purpose |
|---|---|
| `.role-hero-grid` | 2-col flex grid for landing cards |
| `.role-hero-card` | Glassmorphism card with hover lift |
| `.pipeline-strip` | 4-stage progress row |
| `.pipeline-stage` | Individual stage (grey/active/done states) |
| `.result-accordion` | Outer container for 4 panels |
| `.result-panel` | Individual expandable panel |
| `.flag-chip` | Inline flag badge |
| `.flag-chip.critical-high` | Red |
| `.flag-chip.high` | Orange |
| `.flag-chip.low` | Yellow |
| `.flag-chip.normal` | Green |
| `.flag-chip.unknown` | Grey |
| `.lab-table` | Styled table for Panel 3 |
| `.status-badge.pending` | Pulsing orange dot |
| `.status-badge.analyzed` | Solid green checkmark |

**Output:** All visual tokens ready; Sessions UI-2–4 compile without missing class warnings.

**Connects To:** All visual sessions depend on these classes.

**Failure Surface:** None — CSS is additive.

---

## Section D — Progress Checklist

- [ ] **Session UI-1: API Client**
  - [ ] `runPipeline(blob, filename, opts)` function added to `api.ts`
  - [ ] `PipelineResult` interface exported
  - [ ] `LabResult` interface exported
  - [ ] TypeScript compiles with no errors

- [ ] **Session UI-2: RolePicker**
  - [ ] 2-card hero grid rendered (Patient | Doctor)
  - [ ] Clicking Patient card navigates to patient portal
  - [ ] Clicking Doctor card navigates to doctor portal
  - [ ] Glassmorphism / hover effect styles applied

- [ ] **Session UI-3: PatientPortal**
  - [ ] Large upload zone with animated dashed border
  - [ ] Animated progress bar on upload
  - [ ] Report cards show pulsing "Pending" badge for unanalyzed reports
  - [ ] "Analyzed" badge shown in green for analyzed reports

- [ ] **Session UI-4: DoctorPortal**
  - [ ] "Run Pipeline" button on each report card (replaces or supplements "Analyze")
  - [ ] Clicking "Run Pipeline" shows pipeline stage animation
  - [ ] Panel 1: Classification chip + confidence bar visible after run
  - [ ] Panel 2: OCR text shown in scrollable `<pre>` with copy button
  - [ ] Panel 3: Lab results table with CRITICAL_HIGH / HIGH / LOW / NORMAL colour chips
  - [ ] Panel 4: Diagnosis summary + urgent flags + suggested follow-up
  - [ ] Error state handled: toast shown if pipeline call fails
  - [ ] Empty state shown if `lab_report.lab_results` is empty

- [ ] **Session UI-5: CSS**
  - [ ] All flag chip colour classes added
  - [ ] Pipeline strip + stage states (grey / active / done)
  - [ ] Hero card glassmorphism styles
  - [ ] `styles.css` compiles without errors (no broken references)
