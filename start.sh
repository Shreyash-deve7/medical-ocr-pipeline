#!/usr/bin/env bash
# MedVault — Medical Intelligence Ecosystem
# macOS / Linux startup script (equivalent of start.ps1)

set -e

echo "=== MedVault — Medical Intelligence Ecosystem ==="
echo ""

# ── 1. Python virtual environment ───────────────────────────
if [ ! -d ".venv" ]; then
    echo "[1/4] Creating Python virtual environment..."
    python3 -m venv .venv
else
    echo "[1/4] Virtual environment exists."
fi

# ── 2. Install backend dependencies ──────────────────────────
echo "[2/4] Installing Python dependencies..."
.venv/bin/pip install -q -r backend/requirements.txt

# ── 3. Install frontend dependencies ─────────────────────────
echo "[3/4] Installing frontend dependencies..."
(
    cd frontend
    npm install --silent
)

# ── 4. Start servers ─────────────────────────────────────────
echo "[4/4] Starting servers..."
echo ""
echo "  Backend:  http://localhost:3000"
echo "  Frontend: http://localhost:3001"
echo ""

# Start backend in background
export QWEN_VL_SERVER_URL="http://127.0.0.1:8002/v1/chat/completions"
.venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 3000 --reload &
BACKEND_PID=$!

# Start frontend in background
(
    cd frontend
    npx vite --port 3001
) &
FRONTEND_PID=$!

# Wait for either process to exit, then kill both
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT INT TERM
wait
