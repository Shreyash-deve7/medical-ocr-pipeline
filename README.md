# MedVault — Medical OCR Pipeline

A modular medical document OCR pipeline that classifies documents (TABLE / HANDWRITTEN / PRINTED_TEXT) and routes them to the appropriate OCR engine, with LLM-powered structured extraction and a Hepatology knowledge base.

Built with FastAPI + React + TypeScript + SQLite.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.12-blue.svg)
![React](https://img.shields.io/badge/react-19-61dafb.svg)

## Prerequisites

- **Python 3.12**
- **Node.js 20+**
- **NVIDIA GPU** (optional — for GPU acceleration; runs on CPU without it)
- **Windows** (PowerShell) or **macOS/Linux** (bash)

## Quick Start

### 1. Clone the repo

```bash
git clone https://github.com/YOUR_ORG/medvault.git
cd medvault
```

### 2. Run the setup script

```powershell
# Windows
.\start.ps1
```

```bash
# macOS / Linux
chmod +x start.sh
./start.sh
```

This will:
- Create a Python virtual environment (`.venv/`)
- Install backend dependencies (`backend/requirements.txt`)
- Install frontend dependencies (`frontend/package.json`)
- Start the backend on **http://localhost:8000**
- Start the frontend on **http://localhost:5173**

Open **http://localhost:5173** in your browser.

---

## Manual Setup

### Backend

```bash
python -m venv .venv
.venv\Scripts\pip install -r backend\requirements.txt

# Optional: install GPU support for PaddleOCR (RTX 5060 / sm_120)
# Download from: https://paddle-whl.bj.bcebos.com/stable/cu129/paddlepaddle-gpu/paddlepaddle_gpu-3.3.1-cp312-cp312-win_amd64.whl
# Then: .venv\Scripts\pip install paddlepaddle_gpu-3.3.1-cp312-cp312-win_amd64.whl

# Optional: install bitsandbytes for Qwen-VL 4-bit quantization
.venv\Scripts\pip install bitsandbytes>=0.46.1

# Start backend
.venv\Scripts\uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `JWT_SECRET` | `dev-secret-change-me` | JWT signing key (change in production!) |
| `GEMINI_API_KEY` | — | Google Gemini API key for AI analysis |
| `MEDVAULT_STATIC_DIR` | `frontend/dist` | Path to built frontend (for Docker) |
| `MEDVAULT_PRELOAD_GPU` | `1` | Set to `0` to disable GPU model preloading at startup |
| `QWEN_MODEL_PATH` | — | Path to Qwen2.5-VL GGUF model file (if using llama.cpp server) |
| `QWEN_SERVER_URL` | `http://127.0.0.1:8002/v1/chat/completions` | Qwen-VL server endpoint |

---

## Architecture

```
medvault/
├── backend/
│   ├── main.py                  # FastAPI app — pipeline endpoints, SQLite DB
│   ├── document_classifier.py   # 3-class classifier (TABLE/HANDWRITTEN/PRINTED_TEXT)
│   ├── paddle_ocr_provider.py   # PaddleOCR (printed + PP-Structure for tables)
│   ├── qwen_vl_provider.py      # Qwen2.5-VL (handwritten)
│   ├── gpu_manager.py           # GPU preload manager
│   ├── agents/                   # Pipeline agents (classification, OCR, extraction, diagnosis)
│   ├── routes/                   # FastAPI route modules
│   ├── services/                 # Business logic services
│   ├── weights/                  # Trained CNN classifier weights
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── App.tsx               # Router + theme + navigation
│       ├── api.ts                # API client
│       ├── pages/                # Page components
│       └── components/           # Shared components
├── scripts/                      # Training, evaluation, tuning scripts
├── tests/                        # pytest test suite
├── PLAN/                         # Historical planning documents
├── Dockerfile
├── start.ps1
└── README.md
```

---

## Document Classification Pipeline

The pipeline automatically classifies incoming documents:

| Document Type | OCR Engine | Notes |
|---------------|------------|-------|
| **TABLE** | PaddleOCR PP-Structure | Grid/table detection |
| **PRINTED_TEXT** | PaddleOCR | Standard printed text OCR |
| **HANDWRITTEN** | Qwen2.5-VL | Vision-language model |

The classifier uses an ensemble of CNN (MobileNetV3) + heuristic features, achieving **77.4% accuracy** on the 93-image labeled dataset.

---

## API Overview

```
POST   /api/patient/register        # Patient registration
POST   /api/patient/login           # Patient login
POST   /api/patient/upload          # Upload medical report (triggers pipeline)
GET    /api/doctor/patients          # List all patients
POST   /api/doctor/analyze           # Run OCR + AI analysis
GET    /api/gpu/status               # GPU model preload status
POST   /api/gpu/preload              # Trigger GPU model preload
GET    /api/providers/engines        # List available OCR/AI engines
...and 50+ more
```

---

## Tech Stack

- **Backend:** Python 3.12, FastAPI, SQLite (WAL mode), PaddleOCR 2.8.1, Qwen2.5-VL
- **Frontend:** React 19, TypeScript, Vite 6
- **Design:** Custom neumorphic CSS (dark/light mode, responsive)
- **Auth:** PBKDF2 password hashing, JWT tokens
- **GPU:** CUDA 12.x, PaddlePaddle 3.3.1, torch 2.7.1+cu128

---

## Docker

```bash
docker build -t medvault .
docker run -p 8000:8000 medvault
```

Open **http://localhost:8000**

---

## Contributing

1. Fork the repo
2. Create a feature branch (`git checkout -b feat/my-feature`)
3. Commit (`git commit -m "feat: add my feature"`)
4. Push (`git push origin feat/my-feature`)
5. Open a Pull Request

## License

MIT — see [LICENSE](LICENSE)
