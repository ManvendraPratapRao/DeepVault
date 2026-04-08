import json
import shutil
import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile

from app.api.schemas.requests import IngestTextRequest
from app.api.schemas.responses import IngestResponse
from app.core.exceptions import DuplicateDocumentError
from app.dependencies import get_ingestion_service, get_redis_cache
from app.infrastructure.cache.redis import RedisCache
from app.services.ingestion import IngestionService

router = APIRouter()


@router.post("/text", response_model=IngestResponse)
async def ingest_text(request: IngestTextRequest, service: IngestionService = Depends(get_ingestion_service)):
    """Processes raw text directly into the system."""
    try:
        doc = await service.ingest_text(content=request.content, source=request.source, author=request.author)
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
async def ingest_file(file: UploadFile = File(...), service: IngestionService = Depends(get_ingestion_service)):
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


async def _run_async_ingestion(
    job_id: str, request: IngestTextRequest, service: IngestionService, redis_cache: RedisCache
):
    """Background task to run ingestion and update Redis with the result."""
    try:
        await redis_cache.set(f"job:{job_id}", json.dumps({"status": "processing"}), ttl_seconds=86400)
        doc = await service.ingest_text(content=request.content, source=request.source, author=request.author)
        await redis_cache.set(
            f"job:{job_id}",
            json.dumps({"status": "done", "document_id": doc.id, "source": doc.metadata.source}),
            ttl_seconds=86400,
        )
    except DuplicateDocumentError as e:
        await redis_cache.set(
            f"job:{job_id}",
            json.dumps({"status": "done", "document_id": "", "already_existed": True, "message": str(e)}),
            ttl_seconds=86400,
        )
    except Exception as e:
        await redis_cache.set(f"job:{job_id}", json.dumps({"status": "failed", "error": str(e)}), ttl_seconds=86400)


@router.post("/text/async", status_code=202)
async def ingest_text_async(
    request: IngestTextRequest,
    background_tasks: BackgroundTasks,
    service: IngestionService = Depends(get_ingestion_service),
    redis_cache: RedisCache = Depends(get_redis_cache),
):
    """Queues a document for background ingestion, returning a tracker ID immediately."""
    job_id = str(uuid.uuid4())

    # Store initial pending state (TTL 1 day)
    await redis_cache.set(f"job:{job_id}", json.dumps({"status": "pending"}), ttl_seconds=86400)

    # Fire and forget
    background_tasks.add_task(_run_async_ingestion, job_id, request, service, redis_cache)

    return {"job_id": job_id, "status": "pending", "status_url": f"/api/v1/documents/jobs/{job_id}"}


@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str, redis_cache: RedisCache = Depends(get_redis_cache)):
    """Checks the status of an asynchronous ingestion job."""
    raw_status = await redis_cache.get(f"job:{job_id}")
    if not raw_status:
        raise HTTPException(status_code=404, detail="Job not found or expired")

    return json.loads(raw_status)
