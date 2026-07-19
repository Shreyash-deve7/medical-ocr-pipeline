Write-Host "=== MedVault - Medical Intelligence Ecosystem ==="
Write-Host ""

if (-not (Test-Path ".venv")) {
    Write-Host "[1/4] Creating Python virtual environment..."
    python -m venv .venv
} else {
    Write-Host "[1/4] Virtual environment exists."
}

Write-Host "[2/4] Installing Python dependencies..."
.\.venv\Scripts\python -m pip install -q -r backend\requirements.txt

Write-Host "[3/4] Installing frontend dependencies..."
Set-Location frontend
npm install --silent
Set-Location ..

Write-Host "[4/4] Starting servers..."
Write-Host ""
Write-Host "  Backend:  http://localhost:3000"
Write-Host "  Frontend: http://localhost:3001"
Write-Host ""

$backend = Start-Process -NoNewWindow -FilePath "powershell.exe" -ArgumentList "-Command", ".\.venv\Scripts\uvicorn.exe backend.main:app --host 0.0.0.0 --port 3000 --reload" -PassThru
Set-Location frontend
$frontend = Start-Process -NoNewWindow -FilePath "npx.cmd" -ArgumentList "vite --port 3001" -PassThru
Set-Location ..

try {
    Wait-Process -Id $backend.Id, $frontend.Id
} finally {
    Stop-Process -Id $backend.Id, $frontend.Id -ErrorAction SilentlyContinue
}
