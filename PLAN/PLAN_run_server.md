# PLAN — Run Server

## SECTION A — GOAL DEFINITION

### 1. What is being built or changed?
No code modifications or database changes will be performed. The goal is to start the existing MedVault backend (FastAPI/Uvicorn) and frontend (React/Vite) servers, verify they are running, and provide the user with the correct links.

### 2. What does "done" look like?
- Backend server is running at `http://localhost:8000`.
- Frontend server is running at `http://localhost:5173`.
- Links are shared with the user.

### 3. What is explicitly out of scope for this task?
Any edits to code, design refactoring, database schema migration, or new feature additions, unless we encounter startup errors.

---

## SECTION B — TECH STACK

This task runs the existing stack:
- **Backend**: FastAPI with Python 3.12 within a `.venv` virtual environment.
- **Frontend**: React SPA running via Vite.
- **Commands**: PowerShell commands execution in background tasks.

---

## SECTION C — SESSION MODULARIZATION

### Session 1: Run Servers
- **Objective**: Start the backend and frontend servers.
- **Scope**: Start uvicorn backend and vite frontend.
- **Output**: Two running background processes for backend and frontend.
- **Connects to**: Verification and sharing of URLs.
- **Failure Surface**: Port conflict (port 8000 or 5173 already bound), missing Python/Node dependencies, or missing configuration files (e.g. SQLite database).

---

## SECTION D — PROGRESS CHECKLIST

- [x] Session 1: Run Servers
  - [x] Copy `.env.example` to `.env` if `.env` does not exist
  - [x] Start FastAPI Backend server (port 8000)
  - [x] Start React/Vite Frontend server (port 5173)
  - [x] Verify both servers are running and return the links
