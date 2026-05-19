"""POST /api/v1/ingest — Store a memory."""

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field
from typing import Optional


router = APIRouter(prefix="/api/v1", tags=["ingest"])


class IngestRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=100000,
                         description="The text content to store as a memory.")
    namespace: str = Field(default="default", max_length=256)
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    metadata: Optional[dict] = None


@router.post("/ingest")
async def ingest_memory(req: IngestRequest, request: Request):
    """Store a memory and return its metadata."""
    engine = request.app.state.ingest_engine
    result = engine.ingest(
        content=req.content,
        namespace=req.namespace,
        importance=req.importance,
        metadata=req.metadata,
    )
    return result
