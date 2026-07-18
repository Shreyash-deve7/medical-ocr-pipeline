# PLAN — Commit Full Main and Restart Server

## SECTION A — GOAL DEFINITION

### 1. What is being built or changed?
No new code is being written. We will commit the full, correct version of `backend/main.py` and `backend/routes/reports_routes.py` (which contain the route registration and default patient logic), push them to the remote repository, and restart the backend server so the API endpoints are fully functional.

### 2. What does "done" look like?
- `backend/main.py` and `backend/routes/reports_routes.py` changes are committed and pushed to `https://github.com/Shreyash-deve7/medical-ocr-pipeline`.
- Backend server is running successfully on port 8000.
- Querying `/health` and `/api/gpu/status` returns successfully instead of 404.

### 3. What is explicitly out of scope for this task?
Any feature additions or other code changes.

---

## SECTION B — TECH STACK

- **Git**: Committing and pushing.
- **Backend**: FastAPI, Uvicorn.
- **Tools**: PowerShell.

---

## SECTION C — SESSION MODULARIZATION

### Session 1: Commit and Push Correct Files
- **Objective**: Commit the correct full files and push to remote.
- **Scope**: `backend/main.py`, `backend/routes/reports_routes.py`.
- **Output**: Clean git working tree, updated remote repository.
- **Connects to**: Session 2.
- **Failure Surface**: Push conflict.

### Session 2: Start and Verify Servers
- **Objective**: Restart backend and frontend servers, and verify responsiveness.
- **Scope**: Running backend and frontend in background, making HTTP checks.
- **Output**: Functional endpoints.
- **Connects to**: End of task.
- **Failure Surface**: Port binding errors.

---

## SECTION D — PROGRESS CHECKLIST

- [ ] Session 1: Commit and Push Correct Files
  - [ ] Stage and commit `backend/main.py` and `backend/routes/reports_routes.py`
  - [ ] Push changes to `dest main`
- [ ] Session 2: Start and Verify Servers
  - [ ] Start backend server on port 8000
  - [ ] Verify `/health` and `/api/gpu/status` respond successfully
