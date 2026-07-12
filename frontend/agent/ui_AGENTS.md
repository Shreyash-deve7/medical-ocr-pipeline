# AGENTS.md — ui/

## What This Module Is

Vanilla HTML/CSS/JS frontend. No framework, no bundler, no npm. Served as static files by FastAPI's `StaticFiles` mount at `/ui`.

Two pages:
- `patient.html` — patient uploads report images, sees status
- `doctor.html` — doctor sees OCR results, summary, discussion points

---

## File Structure

```
ui/
├── patient.html
├── doctor.html
├── static/
│   ├── css/
│   │   ├── base.css        # Reset, typography, CSS variables
│   │   ├── patient.css
│   │   └── doctor.css
│   └── js/
│       ├── api.js          # ALL fetch calls live here — nowhere else
│       ├── patient.js      # Patient page logic
│       ├── doctor.js       # Doctor page logic
│       └── state.js        # AppState objects for each page
└── AGENTS.md               # ← this file
```

---

## Absolute Rules

1. **All fetch/API calls go through `api.js`** — never write `fetch(...)` inline in HTML or in page JS files
2. **No `<form>` submit with page reload** — all submissions are `event.preventDefault()` + `api.js` call
3. **No global variables** — use the `AppState` object exported from `state.js`
4. **No `innerHTML` with unescaped user/OCR content** — always sanitize before inserting (use `textContent` or a `sanitize()` helper)
5. **No alert/confirm/prompt** — use the UI's own toast/modal components
6. **ES2020+ only** — optional chaining `?.`, nullish coalescing `??`, `async/await` are all fine

---

## api.js — Contract

Every exported function returns `{ data, error, status }`. Callers always check `error` before using `data`.

```javascript
// api.js exports
export async function uploadReport(file, patientId, isHandwritten) { ... }
export async function getReport(reportId) { ... }
export async function getPatientReports(patientId) { ... }
export async function streamSummary(reportId, onChunk, onDone) { ... }  // SSE
export async function retryReport(reportId) { ... }

// Response shape (all endpoints)
// { data: {...}, error: null, status: 200 }
// { data: null, error: "OCR_TIMEOUT", status: 503 }
```

The `streamSummary` function uses the browser `EventSource` API for SSE — do not use fetch streaming for this.

---

## Patient Page (`patient.html` / `patient.js`)

### Flows
1. Patient selects one or more images → preview shown
2. Patient checks "handwritten?" checkbox per image (or auto-detected)
3. Patient submits → `uploadReport()` called per image → `202 Accepted` with `report_id`
4. Each image card shows a status pill: `Uploading → Processing → Done / Error`
5. Polling: `getReport(reportId)` every 2 seconds until `status === 'summary_done'` or `'error'`
6. On `summary_done`: show green checkmark, no further detail on patient side

### AppState shape (patient)
```javascript
const PatientState = {
  patientId: null,           // set at page load from session/URL param
  uploads: [],               // [{ reportId, file, status, isHandwritten }]
  pollingIntervals: {},      // { reportId: intervalId }
};
```

### Rules
- Polling stops automatically on `summary_done` or `error` — always `clearInterval`
- Show a progress bar during upload (use `XMLHttpRequest` for progress events, not fetch)
- Max file size check client-side: 20MB per image, warn if exceeded
- Accepted formats: `image/jpeg`, `image/png`, `image/webp`, `image/tiff`
- Never store the image in localStorage — reference by `reportId` only

---

## Doctor Page (`doctor.html` / `doctor.js`)

### Flows
1. Doctor arrives at page with `?patient_id=...` in URL
2. `getPatientReports(patientId)` loads all reports in `summary_done` state
3. Reports listed in sidebar (newest first)
4. Clicking a report loads its `ocr_fields` + summary into the main panel
5. Summary streams in via SSE (`streamSummary`) — tokens appear as they arrive
6. Discussion points rendered as a checklist — doctor can tick off points during consultation
7. Flagged values (outside normal range) shown in a red-bordered card

### AppState shape (doctor)
```javascript
const DoctorState = {
  patientId: null,
  reports: [],               // [{ reportId, createdAt, status, ocrFields, summary }]
  activeReportId: null,
  checkedPoints: {},         // { reportId: [pointIndex, ...] } — in-memory only
  summaryStream: null,       // active EventSource, or null
};
```

### Rendering Rules
- `ocr_fields` values: always show with units and confidence score
- Confidence < 0.75: show value in amber with a ⚠ icon
- Flagged values (from summary `flags` array): show in red card with normal range
- Discussion points: render as `<ul>` with checkboxes — state is in-memory only (no DB)
- Never show `ocr_raw` — only `ocr_fields`
- If `streamSummary` errors, show a "Retry summary" button that calls `retryReport()`

---

## CSS Conventions

```css
/* Use CSS custom properties for all colors */
:root {
  --color-primary: #2563eb;
  --color-danger: #dc2626;
  --color-warning: #d97706;
  --color-success: #16a34a;
  --color-surface: #f8fafc;
  --color-border: #e2e8f0;
}

/* BEM-lite naming: block__element--modifier */
.report-card { }
.report-card__title { }
.report-card--flagged { border-color: var(--color-danger); }
```

- Mobile-first responsive — the doctor may be on a tablet
- No CSS frameworks (no Tailwind, no Bootstrap)
- Animations only via CSS transitions — no JS animation loops

---

## Security

- Sanitize all text before inserting into DOM:
  ```javascript
  function sanitize(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }
  ```
- Never put `patient_id` or `report_id` in a cookie — URL param or in-memory only
- API calls must include an `Authorization: Bearer <token>` header (stored in memory after login, never localStorage)
- Report images are never fetched back to the frontend after upload

---

## What NOT to Do

- Do not add React, Vue, Alpine, or any JS framework
- Do not write CSS in `<style>` tags in HTML files — use the CSS files
- Do not use `document.write()`
- Do not use `eval()`
- Do not make API calls in `setTimeout` — use `setInterval` with cleanup or SSE
- Do not render summary text as HTML — render as plain text (`textContent`)
