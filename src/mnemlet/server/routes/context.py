"""POST /api/v1/context — Retrieve an agent-friendly Context Pack."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from mnemlet.intelligence.context_pack import build_context_pack
from mnemlet.intelligence.policy import recall_statuses


router = APIRouter(prefix="/api/v1", tags=["context"])


class ContextRequest(BaseModel):
    """Request body for Context Pack recall."""

    query: str = Field(..., min_length=1)
    namespace: Optional[str] = Field(default=None, max_length=256)
    limit: int = Field(default=5, ge=1, le=10)
    min_score: float = Field(default=0.0, ge=0.0, le=1.0)
    include_superseded: bool = False


@router.post("/context")
async def context_pack(req: ContextRequest, request: Request) -> dict:
    """Return a Context Pack for a query."""
    engine = request.app.state.recall_engine
    results = engine.recall(
        query=req.query,
        namespace=req.namespace,
        limit=req.limit,
        min_score=req.min_score,
        include_statuses=recall_statuses(include_superseded=req.include_superseded),
    )
    return build_context_pack(req.query, results, include_superseded=req.include_superseded)
