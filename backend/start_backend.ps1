# start_backend.ps1
# Launches the FastAPI backend using packages installed in the trusted user-space venv.
# The project venv at D:\Projects\...\venv is blocked by Windows Application Control (WDAC).
# This script injects the trusted path so DLLs (pydantic_core, etc.) load correctly.

$trustedSitePackages = "C:\Users\lenovo\venvs\major_ii\Lib\site-packages"

Write-Host "==> Starting Weapon Detection Backend" -ForegroundColor Cyan
Write-Host "==> Using packages from: $trustedSitePackages" -ForegroundColor DarkGray

$env:PYTHONPATH = "$trustedSitePackages;$env:PYTHONPATH"

python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
