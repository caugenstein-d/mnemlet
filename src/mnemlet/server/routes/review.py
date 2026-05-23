"""Review command REST routes for Mnémlet Memory Intelligence."""

from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from mnemlet.constants import (
    MEMORY_TYPE_CONTEXT,
    MEMORY_TYPE_EVENT,
    MEMORY_TYPE_FACT,
    MEMORY_TYPE_INSTRUCTION,
    MEMORY_TYPE_PREFERENCE,
)
from mnemlet.intelligence.review import ReviewService


router = APIRouter(prefix="/api/v1", tags=["review"])


MemoryTypeLiteral = Literal[
    MEMORY_TYPE_CONTEXT,
    MEMORY_TYPE_EVENT,
    MEMORY_TYPE_FACT,
    MEMORY_TYPE_INSTRUCTION,
    MEMORY_TYPE_PREFERENCE,
]


class RememberRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=100000)
    namespace: str = Field(default="default", max_length=256)
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    memory_type: Optional[MemoryTypeLiteral] = None


class ReplaceRequest(BaseModel):
    new_content: str = Field(..., min_length=1, max_length=100000)
    importance: float = Field(default=0.5, ge=0.0, le=1.0)


def _review_service(request: Request) -> ReviewService:
    return ReviewService(request.app.state.db, request.app.state.ingest_engine)


@router.post("/remember")
async def remember_memory(req: RememberRequest, request: Request) -> dict:
    return _review_service(request).remember(req.content, req.namespace, req.importance, req.memory_type)


@router.post("/forget/{memory_id}")
async def forget_memory(memory_id: str, request: Request) -> dict:
    return _review_service(request).forget(memory_id)


@router.post("/replace/{memory_id}")
async def replace_memory(memory_id: str, req: ReplaceRequest, request: Request) -> dict:
    return _review_service(request).replace(memory_id, req.new_content, req.importance)


@router.post("/confirm/{memory_id}")
async def confirm_memory(memory_id: str, request: Request) -> dict:
    return _review_service(request).confirm(memory_id)
