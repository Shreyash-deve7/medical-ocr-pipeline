# MedVault — Setup Guide

> Detailed setup instructions for teammates cloning the repository.

---

## System Requirements

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| Python | 3.12 | 3.12 |
| Node.js | 20 | 22 |
| RAM | 8 GB | 16 GB |
| GPU | — | NVIDIA with 8GB VRAM |
| OS | Windows 10+ | Windows 11 / macOS / Ubuntu 22.04 |

---

## 1. Clone the Repository

```bash
git clone https://github.com/YOUR_ORG/medvault.git
cd medvault
```

---

## 2. Python Environment

```bash
# Create virtual environment
python -m venv .venv

# Activate it
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r backend/requirements.txt
```

### GPU Setup (Optional — for faster OCR)

#### PaddleOCR GPU (Printed Documents)

If you have an **NVIDIA GPU with CUDA 12.x**, install the GPU-enabled PaddlePaddle wheel:

1. Download the wheel for your GPU:
   - **RTX 5060 (sm_120 / Blackwell)**: Use the direct Baidu wheel:
     ```
     https://paddle-whl.bj.bcebos.com/stable/cu129/paddlepaddle-gpu/paddlepaddle_gpu-3.3.1-cp312-cp312-win_amd64.whl
     ```
   - **Other GPUs (CUDA 12.x)**: Try `pip install paddlepaddle-gpu==3.3.1`
   - **CPU only**: No extra install needed — the CPU version is included in `requirements.txt`

2. Install the wheel:
   ```powershell
   .venv\Scripts\pip install paddlepaddle_gpu-3.3.1-cp312-cp312-win_amd64.whl
   ```

#### Qwen-VL GPU Acceleration

For **Qwen2.5-VL handwritten OCR** with 4-bit quantization on GPU:

```bash
pip install bitsandbytes>=0.46.1
```

This enables `BitsAndBytesConfig(load_in_4bit=True)` in the Qwen-VL provider.

---

## 3. Frontend Dependencies

```bash
cd frontend
npm install
cd ..
```

---

## 4. Start the Servers

### Option A: Use the setup script (Windows)

```powershell
.\start.ps1
```

### Option B: Manual start

**Terminal 1 — Backend:**
```bash
.venv\Scripts\uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

**Terminal 2 — Frontend:**
```bash
cd frontend
npm run dev
```

---

## 5. Verify It Works

1. Open **http://localhost:5173** in your browser
2. You should see the MedVault landing page with **Patient Portal** and **Doctor Portal** cards
3. Click **Patient Portal** — you should be auto-logged in and see the upload area
4. Upload a medical document image — it will be classified and OCR'd

---

## Environment Variables

Set these in your shell or a `.env` file in the project root:

| Variable | Default | Description |
|----------|---------|-------------|
| `JWT_SECRET` | `dev-secret-change-me` | JWT signing key. **Change in production!** |
| `GEMINI_API_KEY` | — | Google Gemini API key for AI-powered extraction |
| `MEDVAULT_STATIC_DIR` | `frontend/dist` | Path to built frontend (for Docker) |
| `MEDVAULT_PRELOAD_GPU` | `1` | Set to `0` to disable GPU model preloading |
| `QWEN_SERVER_URL` | `http://127.0.0.1:8002/v1/chat/completions` | Qwen-VL server endpoint |
| `QWEN_MODEL_PATH` | — | Path to Qwen2.5-VL GGUF model file |

---

## GPU Preloading

On startup, the backend preloads models onto the GPU (if available):

- **Classifier CNN** — MobileNetV3 3-class weights
- **PaddleOCR** — GPU-enabled PaddlePaddle
- **Qwen2.5-VL** — 4-bit quantized vision-language model

This happens in a background thread and takes ~10-30 seconds. You can monitor status at:
```
GET http://localhost:8000/api/gpu/status
```

To disable GPU preloading (CPU-only mode):
```powershell
$env:MEDVAULT_PRELOAD_GPU = "0"
```

---

## Troubleshooting

### "ModuleNotFoundError: No module named 'paddle'"
PaddlePaddle is not installed. Run:
```bash
pip install paddlepaddle-gpu==3.3.1
```

### "Using bitsandbytes 4-bit quantization requires bitsandbytes"
Install bitsandbytes:
```bash
pip install bitsandbytes>=0.46.1
```

### "PaddleOCR fails with WinError 127 (missing DLL)"
Apply the Windows DLL fix — see [PaddleOCR Setup](https://github.com/your-org/medvault#paddleocr-setup) in the README.

### "Qwen-VL fails to load"
- Ensure `bitsandbytes` is installed
- If using a custom Qwen server, set `QWEN_SERVER_URL` to your server endpoint
- If running Qwen in-process, ensure `torch` with CUDA is installed

### "Port 8000 already in use"
Change the port:
```bash
.venv\Scripts\uvicorn backend.main:app --host 0.0.0.0 --port 8001 --reload
```
Then update the frontend API base URL in `frontend/src/api.ts`.

### "npm install fails"
- Ensure Node.js 20+ is installed
- Delete `node_modules/` and `frontend/node_modules/` and retry
- If on Windows, try running PowerShell as Administrator

---

## Running Tests

```bash
# Activate venv
.venv\Scripts\activate

# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_classifier.py -v

# Run with coverage
pytest tests/ --cov=backend --cov-report=html
```

---

## Project Structure

```
medvault/
├── backend/
│   ├── main.py                  # FastAPI app entry point
│   ├── document_classifier.py   # 3-class document classifier
│   ├── paddle_ocr_provider.py   # PaddleOCR provider
│   ├── qwen_vl_provider.py     # Qwen-VL provider
│   ├── gpu_manager.py           # GPU preload manager
│   ├── agents/                  # Pipeline agents
│   │   ├── classification_agent.py
│   │   ├── extraction_agent.py
│   │   ├── diagnosis_agent.py
│   │   └── ...
│   ├── routes/                  # FastAPI route modules
│   ├── services/                # Business logic services
│   ├── weights/                  # Trained CNN weights (not in git)
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── api.ts
│   │   ├── pages/
│   │   └── components/
│   └── package.json
├── scripts/                      # Training, evaluation, tuning
│   ├── train_classifier.py
│   ├── eval_classifier.py
│   └── tune_weights.py
├── tests/                        # pytest test suite
├── PLAN/                         # Historical planning docs
├── Dockerfile
├── start.ps1
└── README.md
```

---

## Key Files for Development

| File | Purpose |
|------|---------|
| `backend/main.py` | FastAPI app, all routes, DB setup |
| `backend/document_classifier.py` | 3-class classifier (ensemble CNN + heuristic) |
| `backend/agents/classification_agent.py` | Classification agent with LLM fallback |
| `backend/agents/extraction_agent.py` | LLM-powered structured extraction |
| `backend/agents/ocr_router_agent.py` | Routes OCR based on document class |
| `backend/gpu_manager.py` | GPU model preloading |
| `backend/schemas.py` | Pydantic models (LabReport, etc.) |
| `backend/hepatology_kb.py` | Hepatology reference ranges + clinical patterns |
| `scripts/train_classifier.py` | CNN training script |
| `scripts/eval_classifier.py` | Evaluation script |
| `scripts/tune_weights.py` | Heuristic weight optimization |