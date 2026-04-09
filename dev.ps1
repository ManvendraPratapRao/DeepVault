param (
    [switch]$UI,          # Start the Streamlit Dashboard
    [switch]$DockerOnly   # Only start Qdrant/Redis
)

# 1. Start Infrastructure
Write-Host "`n🚀 Starting DeepVault Infrastructure (Qdrant & Redis)..." -ForegroundColor Cyan
docker compose -f docker/docker-compose.yml up -d

if ($DockerOnly) {
    Write-Host "✅ Infrastructure is up. Exiting as requested." -ForegroundColor Green
    exit
}

# 2. Start UI in background if requested
if ($UI) {
    Write-Host "🎨 Launching DeepVault Arena (Streamlit)..." -ForegroundColor Magenta
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$env:PYTHONPATH='.'; uv run streamlit run app/ui/dashboard.py"
    Write-Host "   -> Access Arena at: http://localhost:8501" -ForegroundColor Gray
}

# 3. Start API (Blocking)
Write-Host "🔥 Launching DeepVault API Server..." -ForegroundColor Green
Write-Host "   -> Documentation: http://localhost:8000/docs" -ForegroundColor Yellow
$env:PYTHONPATH="."
uv run uvicorn app.main:app --reload --port 8000
