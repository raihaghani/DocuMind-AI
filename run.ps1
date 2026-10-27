# ---------------------------------------------------------------------------
# DocuMind AI launcher (Windows PowerShell)
#
# Always runs the project using THIS folder's virtual environment
# (.venv, Python 3.12 with PyMuPDF + scikit-learn), regardless of which
# Python happens to be active in your shell. This avoids the
# "PDF support is not available on the server" error that occurs when the
# server is accidentally started with a different interpreter.
#
# Usage:   .\run.ps1
# ---------------------------------------------------------------------------
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$py = Join-Path $root ".venv\Scripts\python.exe"

if (-not (Test-Path $py)) {
    Write-Host "Virtual environment not found at $py" -ForegroundColor Red
    Write-Host "Create it first:" -ForegroundColor Yellow
    Write-Host "  py -3.12 -m venv .venv"
    Write-Host "  .\.venv\Scripts\python.exe -m pip install -r requirements.txt"
    exit 1
}

# Sanity check: confirm this interpreter can load PDF support.
& $py -c "import fitz, sklearn" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Dependencies missing in .venv. Installing from requirements.txt..." -ForegroundColor Yellow
    & $py -m pip install -r (Join-Path $root "requirements.txt")
}

Write-Host "Starting DocuMind AI with:" -ForegroundColor Green
& $py -c "import sys; print('  ' + sys.executable)"
& $py (Join-Path $root "manage.py") runserver @args
