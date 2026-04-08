from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.schemas.requests import QueryAPIRequest
from app.api.schemas.responses import QueryAPIResponse
from app.core.exceptions import RetrievalError
from app.dependencies import get_query_service
from app.services.query import QueryService

router = APIRouter()


@router.post("", response_model=QueryAPIResponse)
async def query_search(
    request: QueryAPIRequest,
    fastapi_req: Request,
    service: QueryService = Depends(get_query_service),
):
    """Performs a RAG search and returns an AI-generated answer."""
    # We pull the request_id from our Middleware
    request_id = getattr(fastapi_req.state, "request_id", "internal")

    try:
        response = await service.ask(request, request_id=request_id)
        return response
    except RetrievalError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM Generation Error: {str(e)}") from e
