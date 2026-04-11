from fastapi import APIRouter, Depends, HTTPException, Request, Security
from fastapi.security import APIKeyHeader

from app.api.schemas.requests import QueryAPIRequest
from app.api.schemas.responses import QueryAPIResponse
from app.config import settings
from app.core.exceptions import RetrievalError
from app.dependencies import get_query_service
from app.services.query import QueryService

router = APIRouter()
api_key_header = APIKeyHeader(name="X-API-KEY", auto_error=False)


async def get_api_key(api_key: str = Security(api_key_header)):
    if api_key == settings.API_KEY:
        return api_key
    raise HTTPException(status_code=403, detail="Could not validate credentials")


@router.post("", response_model=QueryAPIResponse)
async def query_search(
    request: QueryAPIRequest,
    fastapi_req: Request,
    service: QueryService = Depends(get_query_service),
    _auth: str = Depends(get_api_key),
):
    """Performs a RAG search and returns an AI-generated answer."""
    # We pull the request_id from our Middleware
    request_id = getattr(fastapi_req.state, "request_id", "internal")

    # [SENIOR AUDIT FIX]: We remove the redundant try/except here.
    # Allowing raw exceptions to bubble up to the global handler in main.py
    # ensures that we get full tracebacks and structured error responses
    # instead of masked 'HTTPException' 500s.
    response = await service.ask(request, request_id=request_id)
    return response
