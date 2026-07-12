"""
diagnose_gpu.py - GPU environment diagnostic for pipeline_v1
============================================================
Verifies BOTH OCR backends run on the system GPU using pure native stacks:
  - PaddleOCR  (printed reports)  via paddlepaddle-gpu CUDA
  - Qwen2.5-VL (handwritten)      via torch CUDA  (separate :8002 microservice)

NO RapidOCR / DirectML is used (native PaddlePaddle + native torch only).

Run with:  ..\\venv\\Scripts\\python.exe diagnose_gpu.py
"""
import sys
import os
import platform

# Force UTF-8 output
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

NVIDIA_SMI = r"C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe"

print("=" * 60)
print("GPU ENVIRONMENT DIAGNOSTIC  (pipeline_v1)")
print("=" * 60)
print(f"Platform: {platform.system()} {platform.release()}")
print(f"Python:   {sys.version.splitlines()[0]}")
print()

# ---- PaddlePaddle (printed OCR, native CUDA) ----
print("[1/3] Checking PaddlePaddle (PaddleOCR printed OCR, native CUDA)...")
paddle_ok = False
try:
    import paddle
    print(f"  PaddlePaddle version:   {paddle.__version__}")
    print(f"  Compiled with CUDA:     {paddle.is_compiled_with_cuda()}")
    device = paddle.device.get_device()
    print(f"  Active device:          {device}")
    if "gpu" in device:
        print("  PaddleOCR GPU active!")
        paddle_ok = True
    else:
        print("  NOTE: PaddlePaddle is on CPU (RTX 5060 needs paddle>=3.x).")
except Exception as e:
    print(f"  FAILED: {e}")

print()

# ---- torch (Qwen2.5-VL handwritten OCR, native CUDA) ----
# Checked in a SEPARATE subprocess on purpose: PaddlePaddle prepends its own
# CUDA/CUDNN DLLs to PATH on import, which breaks torch's CUDNN load if both
# live in one process. In production Qwen-VL runs in its own :8002 process,
# so this mirrors reality and reports an honest result.
print("[2/3] Checking torch (Qwen2.5-VL handwritten OCR, native CUDA)...")
torch_ok = False
try:
    import subprocess
    probe = (
        "import torch, sys; "
        "print('torch', torch.__version__); "
        "print('avail', torch.cuda.is_available()); "
        "print('device', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'NONE'); "
        "x=torch.randn(512,512,device='cuda'); (x@x).sum(); "
        "print('matmul OK'); "
        "print('cap', torch.cuda.get_device_capability(0))"
    )
    res = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True, text=True, timeout=120,
    )
    sys.stdout.write(res.stdout)
    if res.stderr:
        for line in res.stderr.splitlines():
            if "Warning" not in line and line.strip():
                print(f"  [torch stderr] {line}")
    torch_ok = res.returncode == 0 and "matmul OK" in res.stdout
    if not torch_ok:
        print("  NOTE: torch CUDA check failed in subprocess.")
except Exception as e:
    print(f"  FAILED: {e}")

print()

# ---- nvidia-smi snapshot ----
print("[3/3] GPU memory snapshot (nvidia-smi)...")
if os.path.exists(NVIDIA_SMI):
    os.system(
        f'"{NVIDIA_SMI}" --query-gpu=name,memory.used,memory.total,utilization.gpu '
        "--format=csv,noheader"
    )
else:
    print("  nvidia-smi not found at expected path; skipping.")

print()
print("=" * 60)
print("SUMMARY")
print("=" * 60)
print(f"  PaddlePaddle CUDA (printed):   {'PASS' if paddle_ok else 'FAIL'}")
print(f"  torch CUDA (handwritten):      {'PASS' if torch_ok else 'FAIL'}")
print()
if paddle_ok and torch_ok:
    print("SUCCESS: Both OCR backends run on the system GPU (native stacks).")
    print("  PaddleOCR (printed) -> PaddlePaddle CUDA (in-process)")
    print("  Qwen2.5-VL (handwritten) -> torch CUDA (separate :8002 process)")
    print()
    print("  IMPORTANT: Never run both GPU models in the SAME process")
    print("  (Hard Rule #2). Qwen runs in its own microservice process.")
else:
    print("PARTIAL/FAILED: Fix versions in pipeline_v1/backend/requirements.txt.")
print("=" * 60)
