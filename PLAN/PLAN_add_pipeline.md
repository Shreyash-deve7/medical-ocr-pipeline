# PLAN_add_pipeline

## GOAL DEFINITION
We need to introduce a "pipeline" option in the OCR engine settings that explicitly routes printed reports to PaddleOCR and handwritten reports to Qwen2.5-VL. Currently, there is an "auto" option that performs this behavior using the `AutoOCRProvider`. We will replace the "auto" option with a "pipeline" option (or rename it) to make this fixed pipeline explicit in the UI and backend options.

**What success looks like:**
- The frontend Settings page will show a "Pipeline" option for OCR engines.
- Selecting this option will correctly route documents to PaddleOCR (for printed) and Qwen2.5-VL (for handwritten).
- The backend configuration will recognize the "pipeline" engine type and instantiate the appropriate provider.

**Out of scope:**
- Modifying the actual classification logic or the underlying PaddleOCR / Qwen2.5-VL implementations.

## TECH STACK
- **Backend:** Python, FastAPI (`main.py`)
- **Frontend:** React, TypeScript (`Settings.tsx`)

## SESSION MODULARIZATION

### Session 1: Backend Configuration Updates
- **Objective:** Update the backend to support the "pipeline" OCR engine option.
- **Scope:** `backend/main.py`
- **Output:** The `OCR_ENGINES` dictionary supports the `"pipeline"` key. The `/api/providers/engines` endpoint returns the `"pipeline"` option instead of `"auto"`.
- **Connects to:** Frontend Settings UI. If the backend doesn't expose `"pipeline"`, the frontend won't show it in the dropdown.
- **Failure Surface:** Existing database records with `engine="auto"` might fail to load if we completely remove `"auto"`. *[ASSUMPTION: We should keep `"auto"` in `OCR_ENGINES` for backward compatibility but remove it from `list_engines` so new providers use `"pipeline"`]*

### Session 2: Frontend UI Updates
- **Objective:** Update the Settings UI to properly render the new "pipeline" option with an appropriate icon.
- **Scope:** `frontend/src/pages/Settings.tsx`
- **Output:** The `ENGINE_ICONS` mapping handles the `"pipeline"` key.
- **Connects to:** Final verification. 
- **Failure Surface:** The UI might show a missing icon or incorrect name if the ID mapping isn't updated.

## PROGRESS CHECKLIST

- [ ] Session 1: Backend Configuration Updates
  - [ ] Add `"pipeline"` to `OCR_ENGINES` in `main.py` mapping to `AutoOCRProvider`.
  - [ ] Update `list_engines` endpoint to return `"pipeline"` instead of `"auto"` with the name `"Pipeline (PaddleOCR ↔ Qwen2.5-VL)"`.
  - [ ] Ensure backward compatibility by keeping `"auto"` in `OCR_ENGINES` temporarily.
- [ ] Session 2: Frontend UI Updates
  - [ ] Update `ENGINE_ICONS` in `Settings.tsx` to include `"pipeline"`.
  - [ ] Verify the Settings page correctly allows adding the "Pipeline" provider.
