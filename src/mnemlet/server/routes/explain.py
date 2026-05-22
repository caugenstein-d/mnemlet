"""GET /api/v1/explain/{memory_id} — Explain a stored memory."""

from __future__ import annotations

from fastapi import APIRouter, Request

from mnemlet.intelligence.provenance import explain_memory


router = APIRouter(prefix="/api/v1", tags=["explain"])


@router.get("/explain/{memory_id}")
async def explain(memory_id: str, request: Request) -> dict:
    return explain_memory(request.app.state.db, memory_id)
