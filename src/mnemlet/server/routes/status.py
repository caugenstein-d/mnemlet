"""GET /api/v1/status and /api/v1/health — System status."""

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from mnemlet import __version__


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
        "version": __version__,
    }


@router.get("/vault")
async def vault_info(request: Request):
    """Get vault path and file count."""
    vault = request.app.state.vault
    count = sum(1 for _ in vault.vault_path.rglob("*.md"))
    return {"vault_path": str(vault.vault_path), "file_count": count}


class DecayConfigRequest(BaseModel):
    lambda_: float = Field(default=0.01, ge=0.0, le=1.0, alias="lambda")
    purge_threshold: float = Field(default=0.05, ge=0.0, le=1.0)
    hard_delete_threshold: float = Field(default=0.01, ge=0.0, le=1.0)
    hard_delete_age_days: int = Field(default=90, ge=1)


@router.get("/namespaces/{namespace}/decay")
async def get_decay_config(namespace: str, request: Request):
    """Get decay configuration for a namespace."""
    config = request.app.state.db.get_decay_config(namespace)
    if config is None:
        return {
            "namespace": namespace, "lambda": 0.01, "purge_threshold": 0.05,
            "hard_delete_threshold": 0.01, "hard_delete_age_days": 90,
            "note": "using defaults — no custom config set",
        }
    return config


@router.put("/namespaces/{namespace}/decay")
async def set_decay_config(namespace: str, req: DecayConfigRequest, request: Request):
    """Set decay configuration for a namespace."""
    config = request.app.state.db.set_decay_config(
        namespace=namespace,
        lambda_=req.lambda_,
        purge_threshold=req.purge_threshold,
        hard_delete_threshold=req.hard_delete_threshold,
        hard_delete_age_days=req.hard_delete_age_days,
    )
    return config
