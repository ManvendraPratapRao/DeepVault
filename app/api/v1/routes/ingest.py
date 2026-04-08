import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.api.schemas.requests import IngestTextRequest
from app.api.schemas.responses import IngestResponse
from app.core.exceptions import DuplicateDocumentError
from app.dependencies import get_ingestion_service
from app.services.ingestion import IngestionService

router = APIRouter()


@router.post("/text", response_model=IngestResponse)
async def ingest_text(
    request: IngestTextRequest, service: IngestionService = Depends(get_ingestion_service)
):
    """Processes raw text directly into the system."""
    try:
        doc = await service.ingest_text(
            content=request.content, source=request.source, author=request.author
        )
        return IngestResponse(
            document_id=doc.id,
            source=doc.metadata.source,
            chunks_created=0,  # Service returns Document, chunks are internal
            message="Text ingested successfully",
        )
    except DuplicateDocumentError as e:
        return IngestResponse(
            document_id="",
            source=request.source,
            chunks_created=0,
            already_existed=True,
            message=str(e),
        )


@router.post("/file", response_model=IngestResponse)
async def ingest_file(
    file: UploadFile = File(...), service: IngestionService = Depends(get_ingestion_service)
):
    """Saves an uploaded file to a temp path and processes it."""
    # Create a temp file to allow PyMuPDF or Path.read_text to access it
    suffix = Path(file.filename).suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)

    try:
        doc = await service.ingest_file(tmp_path)
        return IngestResponse(
            document_id=doc.id,
            source=doc.metadata.source,
            chunks_created=0,
            message=f"File '{file.filename}' processed and indexed",
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    finally:
        if tmp_path.exists():
            tmp_path.unlink()
