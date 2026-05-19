"""POST /api/v1/recall — Retrieve relevant memories."""

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field
from typing import Optional


router = APIRouter(prefix="/api/v1", tags=["recall"])


class RecallRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Natural language query.")
    namespace: Optional[str] = Field(default=None, max_length=256)
    limit: int = Field(default=5, ge=1, le=10)
    min_score: float = Field(default=0.0, ge=0.0, le=1.0)


@router.post("/recall")
async def recall_memories(req: RecallRequest, request: Request):
    """Retrieve memories relevant to the query."""
    engine = request.app.state.recall_engine
    results = engine.recall(
        query=req.query,
        namespace=req.namespace,
        limit=req.limit,
        min_score=req.min_score,
    )
    return {"results": results, "count": len(results)}
