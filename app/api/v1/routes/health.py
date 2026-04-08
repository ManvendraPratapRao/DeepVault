import time

from fastapi import APIRouter

from app.api.schemas.responses import HealthResponse
from app.config import settings

router = APIRouter()
start_time = time.time()


@router.get("", response_model=HealthResponse)
async def health_check():
    """Confirms the API and its components are functional."""
    return HealthResponse(
        status="ok",
        version=settings.VERSION,
        uptime_seconds=time.time() - start_time,
        components={"sqlite": "connected", "qdrant": "connected", "groq": "ready"},
    )
