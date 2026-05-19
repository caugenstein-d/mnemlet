"""POST /api/v1/decay/run — Manual decay and purge trigger."""

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field


router = APIRouter(prefix="/api/v1", tags=["decay"])


class DecayRunRequest(BaseModel):
    limit: int = Field(default=500, ge=1, le=10000)
    purge_threshold: float = Field(default=0.05, ge=0.0, le=1.0)
    hard_delete_threshold: float = Field(default=0.01, ge=0.0, le=1.0)
    hard_delete_age_days: int = Field(default=90, ge=1)
    dry_run: bool = Field(default=False)


@router.post("/decay/run")
async def run_decay(req: DecayRunRequest, request: Request):
    """Manually trigger decay processing and purging."""
    from engram.engine.decay import DecayEngine

    decay = DecayEngine(request.app.state.db)

    decay_result = decay.decay_all_active(limit=req.limit)
    purge_result = decay.run_purge(
        purge_threshold=req.purge_threshold,
        hard_delete_threshold=req.hard_delete_threshold,
        hard_delete_age_days=req.hard_delete_age_days,
        dry_run=req.dry_run,
    )

    return {
        "decay": decay_result,
        "purge": purge_result,
        "dry_run": req.dry_run,
    }
