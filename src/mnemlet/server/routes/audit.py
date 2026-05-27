"""GET /api/v1/audit - read-only audit log."""

from __future__ import annotations

from fastapi import APIRouter, Query, Request


router = APIRouter(prefix="/api/v1", tags=["audit"])


@router.get("/audit")
async def audit_log(
    request: Request,
    namespace: str | None = None,
    action: str | None = None,
    since: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, object]:
    """Return recent audit events."""
    events = request.app.state.db.query_audit(namespace=namespace, action=action, since=since, limit=limit)
    return {"events": events, "count": len(events)}
