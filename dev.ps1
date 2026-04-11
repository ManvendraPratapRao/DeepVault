param (
    [switch]$UI
)

# Environment
$env:PYTHONPATH = "."
$env:PYTHONUTF8 = 1

# Infra
Write-Host "Starting Infra..."
docker compose -f docker/docker-compose.yml up -d redis qdrant

# API
Write-Host "Starting Hardened API..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", "uv run uvicorn app.main:app --host 0.0.0.0 --port 8000"

# UI
if ($UI) {
    Write-Host "Starting Arena UI..."
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "uv run streamlit run app/ui/dashboard.py"
}

Write-Host "Ready."
