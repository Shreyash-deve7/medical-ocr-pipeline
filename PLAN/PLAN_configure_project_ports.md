# PLAN - Configure Project Ports

## SECTION A — GOAL DEFINITION
1. **What is being built or changed?**
   - Create a file `ports.md` in the workspace root detailing the selected port range (`3000-3009`) and assigning specific ports to the project services.
   - Detect and modify any hardcoded ports in the startup scripts (`start.ps1`, `start.sh`) and codebase (`backend/main.py`, `frontend/vite.config.ts`) to use the newly selected ports in the range `3000-3009`.
2. **What does "done" look like?**
   - `ports.md` exists in the workspace root and states the port assignments (e.g. Backend: `3000`, Frontend: `3001`).
   - The startup scripts `start.ps1` and `start.sh` are updated to use port `3000` for the backend and `3001` for the frontend.
   - Vite proxy and configuration (`frontend/vite.config.ts`) and CORS origins (`backend/main.py`) are updated to match the new ports.
   - Running the startup script launches the services successfully on these ports.
3. **What is explicitly out of scope?**
   - Modifying docker configs (unless requested, but none exist targeting these exact ports for host binding, docker-compose is not present).
   - Changing third-party model servers (like Qwen on `8002` or Nvidia NIM endpoints) which are external services.

## SECTION B — TECH STACK
- **Configuration File**: Markdown (`ports.md`).
- **Scripts modified**: PowerShell (`start.ps1`), Bash (`start.sh`).
- **Codebase files modified**: TypeScript/Vite (`frontend/vite.config.ts`), Python/FastAPI (`backend/main.py`).

## SECTION C — SESSION MODULARIZATION
### Session 1: Create `ports.md` and Update Configs/Codebase
- **Objective**: Create `ports.md` with chosen ports (Backend: 3000, Frontend: 3001). Update `backend/main.py` CORS origins and `frontend/vite.config.ts` port/proxy configuration to use the new ports.
- **Scope**: Create `ports.md`, modify `backend/main.py`, modify `frontend/vite.config.ts`.
- **Output**: Port definitions documented, application configurations aligned.
- **Connects to**: Session 2 (modifying startup scripts).
- **Failure Surface**: Backend/Frontend CORS or proxy mismatches. We will ensure all connections align exactly.

### Session 2: Update Startup Scripts and Verify
- **Objective**: Update port configurations in `start.ps1` and `start.sh` to match the new ports, and run a validation to verify it boots up correctly.
- **Scope**: Modify `start.ps1` and `start.sh`.
- **Output**: Startup scripts updated and verified.
- **Failure Surface**: Startup scripts failing due to syntax errors or ports still blocked. We will double-check syntax and verify port availability (which we know are free from the previous scan).

## SECTION D — PROGRESS CHECKLIST
- [x] Session 1: Create ports.md and Update Application Configs
  - [x] Create `ports.md` in workspace root and select Backend: `3000`, Frontend: `3001`
  - [x] Modify `backend/main.py` CORS middleware to allow `localhost:3001` and `127.0.0.1:3001`
  - [x] Modify `frontend/vite.config.ts` to run on `3001` and proxy to backend at `3000`
- [x] Session 2: Update Startup Scripts and Verify
  - [x] Modify `start.ps1` port args (backend to `3000`, frontend to `3001`) and console URLs
  - [x] Modify `start.sh` port args (backend to `3000`, frontend to `3001`) and console URLs
  - [x] Run a quick smoke check to ensure no syntax errors and script starts successfully
