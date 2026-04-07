from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from app.api.schemas.responses import DocumentListResponse, DocumentSummary
from app.dependencies import get_document_service
from app.services.document import DocumentService

router = APIRouter()

@router.get("", response_model=DocumentListResponse)
async def list_documents(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    service: DocumentService = Depends(get_document_service)
):
    """Returns a paginated list of all stored documents."""
    docs = await service.list_documents(limit=limit, offset=offset)
    
    summaries = [
        DocumentSummary(
            id=d.id,
            source=d.metadata.source,
            author=d.metadata.author,
            created_at=str(d.metadata.created_at),
            version=d.version
        ) for d in docs
    ]
    
    return DocumentListResponse(
        documents=summaries,
        total=len(summaries), # Note: In Phase 4 we will add a real 'total' count
        limit=limit,
        offset=offset
    )

@router.delete("/{doc_id}", status_code=204)
async def delete_document(
    doc_id: str,
    service: DocumentService = Depends(get_document_service)
):
    """Deletes a document and its chunks from all stores."""
    try:
        await service.delete_document(doc_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
