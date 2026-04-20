from fastapi import APIRouter, Depends, HTTPException, Request, Security
from fastapi.security import APIKeyHeader

from app.api.schemas.requests import QueryAPIRequest
from app.api.schemas.responses import QueryAPIResponse
from app.config import settings
from app.core.models.query import QueryRequest
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

    # Map API request schema → internal service model
    service_request = QueryRequest(
        query_text=request.query_text,
        top_k=request.top_k,
        chunking_strategy=request.chunking_strategy,
        retrieval_strategy=request.retrieval_strategy,
        use_query_rewriting=request.use_query_rewriting,
        user_id=request.user_id,
        session_id=request.session_id,
        filters=request.filters,
    )

    response = await service.ask(service_request, request_id=request_id)
    return response
