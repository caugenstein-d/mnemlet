"""GET /api/v1/memories — read-only memory listing and detail for the dashboard."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request


router = APIRouter(prefix="/api/v1", tags=["memories"])


def _split_frontmatter(text: str) -> tuple[str, str]:
    """Split a vault Markdown file into (raw frontmatter, content body)."""
    if not text.startswith("---"):
        return "", text
    lines = text.split("\n")
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            frontmatter = "\n".join(lines[1:i])
            content = "\n".join(lines[i + 1:]).lstrip("\n")
            return frontmatter, content
    return "", text


def _display_path(path: Path) -> str:
    """Render an absolute path with the user's home directory as ``~``."""
    home = str(Path.home())
    raw = str(path)
    if raw.startswith(home):
        return "~" + raw[len(home):]
    return raw


@router.get("/memories")
async def list_memories(
    request: Request,
    namespace: str | None = None,
    sort: str = Query(default="last_accessed_at"),
    order: str = Query(default="desc"),
    limit: int = Query(default=50, ge=1, le=5000),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    """Return a paginated page of memories plus the namespace list for filtering."""
    db = request.app.state.db
    memories = db.list_memories_page(
        namespace=namespace, sort_by=sort, order=order, limit=limit, offset=offset
    )
    return {
        "memories": memories,
        "total": db.count_memories(namespace=namespace),
        "limit": limit,
        "offset": offset,
        "namespace": namespace,
        "namespaces": db.list_namespaces(),
    }


@router.get("/memories/{memory_id}")
async def get_memory_detail(memory_id: str, request: Request) -> dict[str, Any]:
    """Return a single memory with full vault content, frontmatter, and trust block."""
    db = request.app.state.db
    vault = request.app.state.vault

    memory = db.get_memory(memory_id)
    if memory is None:
        raise HTTPException(status_code=404, detail=f"Memory {memory_id} not found")

    namespace = memory.get("namespace", "default")
    try:
        metadata = json.loads(memory.get("metadata_json") or "{}")
    except json.JSONDecodeError:
        metadata = {}

    file_path = vault.find_memory_file(namespace, memory_id)
    if file_path is not None:
        raw = file_path.read_text()
        frontmatter, content = _split_frontmatter(raw)
        file_info = {
            "path": str(file_path),
            "display_path": _display_path(file_path),
            "exists": True,
        }
    else:
        # Legacy or system memories may have no vault file; fall back to the
        # preview stored in SQLite so the detail view still renders something.
        frontmatter = ""
        content = memory.get("content_preview", "")
        file_info = {
            "path": None,
            "display_path": _display_path(vault.vault_path / namespace),
            "exists": False,
        }

    return {
        "id": memory_id,
        "namespace": namespace,
        "status": memory.get("status"),
        "memory_type": memory.get("memory_type"),
        "type_confidence": memory.get("type_confidence"),
        "type_source": memory.get("type_source"),
        "retention_score": memory.get("retention_score"),
        "importance": memory.get("importance"),
        "created_at": memory.get("created_at"),
        "last_accessed_at": memory.get("last_accessed_at"),
        "access_count": memory.get("access_count"),
        "superseded_by": memory.get("superseded_by"),
        "content_summary": memory.get("content_summary"),
        "content": content,
        "frontmatter": frontmatter,
        "metadata": metadata,
        "trust": {
            "ingested_by": memory.get("ingested_by") or "legacy",
            "caller_identity": memory.get("caller_identity") or "unknown",
            "secret_guard_result": memory.get("secret_guard_result") or "legacy",
            "confirmation_count": memory.get("confirmation_count") or 0,
            "forgotten": memory.get("status") == "forgotten",
            "replaced_by": memory.get("superseded_by"),
        },
        "file": file_info,
    }
