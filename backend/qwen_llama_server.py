"""
qwen_llama_server.py - Qwen2.5-VL handwritten OCR microservice via llama.cpp (GPU, FAST)
=====================================================================================
Primary handwritten-OCR backend. The official llama.cpp CUDA binary
(llama_cpp_bin/llama-server.exe) decodes far faster than torch transformers on this
RTX 5060 (Blackwell) and keeps us well under the 10s per-image budget.

Why an external binary and not the `llama_cpp` Python wheel?
  The installed llama_cpp_python 0.3.33 has the vision helper code but NO registered
  multimodal chat handler, so images are silently dropped. The prebuilt llama.cpp
  server binary fully supports Qwen2-VL vision via --mmproj.

Uses the local GGUF + mmproj already in e2e_pipeline/models (no download).
Serves an OpenAI-compatible /v1/chat/completions endpoint.

Run with:
    ..\\venv\\Scripts\\python.exe qwen_llama_server.py
    (launches llama-server.exe on http://127.0.0.1:8002)

Matches the project's earlier fast path: "a local llama.cpp server running a
Qwen-VL model" (torch transformers qwen_vl_server.py is the fallback).
"""
import os
import subprocess
import sys

# script lives at <root>/pipeline_v1/backend/qwen_llama_server.py -> go up 3 levels
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BIN = os.environ.get(
    "LLAMA_SERVER_BIN",
    os.path.join(ROOT, "llama_cpp_bin", "llama-server.exe"),
)
MODEL_PATH = os.environ.get(
    "QWEN_GGUF",
    os.path.join(ROOT, "e2e_pipeline", "models", "Qwen2.5-VL-3B-Instruct-Q4_K_M.gguf"),
)
MMPROJ_PATH = os.environ.get(
    "QWEN_MMPROJ",
    os.path.join(ROOT, "e2e_pipeline", "models", "Qwen2.5-VL-3B-Instruct-mmproj-f16.gguf"),
)
PORT = int(os.environ.get("QWEN_PORT", "8002"))
N_GPU_LAYERS = int(os.environ.get("QWEN_N_GPU_LAYERS", "99"))
N_CTX = int(os.environ.get("QWEN_CTX", "4096"))

if not os.path.exists(BIN):
    raise SystemExit(f"[QwenLlama] llama-server binary not found: {BIN}\n"
                     f"  Download from https://github.com/ggml-org/llama.cpp/releases "
                     f"(llama-*-bin-win-cuda-12.4-x64.zip) and extract to llama_cpp_bin/.")
if not os.path.exists(MODEL_PATH):
    raise SystemExit(f"[QwenLlama] GGUF not found: {MODEL_PATH}")
if not os.path.exists(MMPROJ_PATH):
    raise SystemExit(f"[QwenLlama] mmproj not found: {MMPROJ_PATH}")

print(f"[QwenLlama] binary : {BIN}")
print(f"[QwenLlama] model  : {MODEL_PATH}")
print(f"[QwenLlama] mmproj : {MMPROJ_PATH}")
print(f"[QwenLlama] gpu_layers={N_GPU_LAYERS} ctx={N_CTX} port={PORT}")

cmd = [
    BIN,
    "--model", MODEL_PATH,
    "--mmproj", MMPROJ_PATH,
    "--n-gpu-layers", str(N_GPU_LAYERS),
    "--ctx-size", str(N_CTX),
    "--port", str(PORT),
    "--host", "127.0.0.1",
]

# Launch the GPU microservice and stay alive as its parent process.
proc = subprocess.Popen(cmd)
try:
    proc.wait()
except KeyboardInterrupt:
    proc.terminate()
    raise
