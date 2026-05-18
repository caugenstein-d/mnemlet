"""GET /api/v1/status and /api/v1/health — System status."""

from fastapi import APIRouter, Request


router = APIRouter(prefix="/api/v1", tags=["status"])


@router.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}


@router.get("/status")
async def status(request: Request):
    """System status with memory counts."""
    db = request.app.state.db
    chroma = request.app.state.chroma

    active = db.conn.execute(
        "SELECT COUNT(*) FROM memories WHERE status = 'active'"
    ).fetchone()[0]
    cold = db.conn.execute(
        "SELECT COUNT(*) FROM memories WHERE status = 'cold_storage'"
    ).fetchone()[0]
    interactions = db.conn.execute(
        "SELECT COUNT(*) FROM interactions"
    ).fetchone()[0]
    chroma_count = chroma.count()

    return {
        "active_memories": active,
        "cold_storage_memories": cold,
        "total_interactions": interactions,
        "chroma_documents": chroma_count,
        "version": "0.1.0",
    }
