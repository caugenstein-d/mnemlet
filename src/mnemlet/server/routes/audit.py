"""GET /api/v1/audit - read-only audit log."""

from __future__ import annotations

from fastapi import APIRouter, Query, Request


router = APIRouter(prefix="/api/v1", tags=["audit"])


@router.get("/audit")
async def audit_log(
    request: Request,
    namespace: str | None = None,
    action: str | None = None,
    result: str | None = None,
    since: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> dict[str, object]:
    """Return audit events with optional filters and pagination."""
    db = request.app.state.db
    events = db.query_audit(
        namespace=namespace, action=action, result=result,
        since=since, limit=limit, offset=offset,
    )
    return {
        "events": events,
        "count": len(events),
        "total": db.count_audit(namespace=namespace, action=action, result=result, since=since),
        "limit": limit,
        "offset": offset,
    }
