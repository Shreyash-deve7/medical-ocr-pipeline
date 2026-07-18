<#
.SYNOPSIS
Sets up the Python 3.12 development environment for the OCR pipeline using uv.

.DESCRIPTION
This script creates a Python 3.12 virtual environment and installs the exact
PaddlePaddle CUDA 12.9 wheel required for GPU-accelerated OCR, followed by
the project's pinned dependencies.

.NOTES
- Requires uv (https://docs.astral.sh/uv/)
- Requires Python 3.12 to be discoverable by uv (uv python install 3.12)
- Intended for Windows PowerShell
#>

param(
    [switch]$SkipActivate
)

$ErrorActionPreference = 'Stop'

Write-Host "`n=== Environment Setup: Python 3.12 + PaddlePaddle CUDA 12.9 ===" -ForegroundColor Cyan

# ---------------------------------------------------------------------------
# 1. Verify uv is available
# ---------------------------------------------------------------------------
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: 'uv' is not installed or not in PATH." -ForegroundColor Red
    Write-Host "Install it from https://docs.astral.sh/uv/ and retry." -ForegroundColor Yellow
    exit 1
}

Write-Host "[1/4] uv found: $(uv --version)" -ForegroundColor Green

# ---------------------------------------------------------------------------
# 2. Create Python 3.12 virtual environment
# ---------------------------------------------------------------------------
$VenvDir = ".venv"
if (Test-Path $VenvDir) {
    Write-Host "Virtual environment '$VenvDir' already exists. Removing it..." -ForegroundColor Yellow
    Remove-Item $VenvDir -Recurse -Force
}

Write-Host "[2/4] Creating Python 3.12 virtual environment..." -ForegroundColor Green
uv venv --python 3.12 $VenvDir

if (-not $?) {
    Write-Host "ERROR: Failed to create Python 3.12 virtual environment." -ForegroundColor Red
    Write-Host "Ensure Python 3.12 is installed: uv python install 3.12" -ForegroundColor Yellow
    exit 1
}

Write-Host "Virtual environment created at $VenvDir" -ForegroundColor Green

# ---------------------------------------------------------------------------
# 3. Install PaddlePaddle GPU wheel (Baidu CUDA 12.9 build) first
# ---------------------------------------------------------------------------
$PaddleWheelUrl = "https://paddle-whl.bj.bcebos.com/stable/cu129/paddlepaddle-gpu/paddlepaddle_gpu-3.3.1-cp312-cp312-win_amd64.whl"

Write-Host "[3/4] Installing PaddlePaddle GPU 3.3.1 (CUDA 12.9) from Baidu wheel..." -ForegroundColor Green
Write-Host "  URL: $PaddleWheelUrl" -ForegroundColor DarkGray

uv pip install $PaddleWheelUrl --python $VenvDir

if (-not $?) {
    Write-Host "ERROR: Failed to install PaddlePaddle GPU wheel." -ForegroundColor Red
    Write-Host "Check network connectivity and retry." -ForegroundColor Yellow
    exit 1
}

Write-Host "PaddlePaddle GPU 3.3.1 installed successfully." -ForegroundColor Green

# ---------------------------------------------------------------------------
# 4. Install remaining project dependencies
# ---------------------------------------------------------------------------
Write-Host "[4/4] Installing project dependencies from backend/requirements.txt..." -ForegroundColor Green

uv pip install -r backend/requirements.txt --python $VenvDir

if (-not $?) {
    Write-Host "ERROR: Failed to install project dependencies." -ForegroundColor Red
    exit 1
}

Write-Host "`n=== Setup Complete ===" -ForegroundColor Cyan
Write-Host "Virtual environment: $VenvDir" -ForegroundColor Green
Write-Host "`nTo activate the environment, run:" -ForegroundColor Yellow
Write-Host "  .\$VenvDir\Scripts\Activate.ps1" -ForegroundColor White
Write-Host "`nThen verify PaddlePaddle GPU:" -ForegroundColor Yellow
Write-Host "  python -c `"import paddle; print(paddle.__version__); print(paddle.device.is_compiled_with_cuda())`"" -ForegroundColor White
Write-Host "`nTo run the pipeline:" -ForegroundColor Yellow
Write-Host "  python pipeline.py --input <test-image> --output result.json" -ForegroundColor White
Write-Host ""
