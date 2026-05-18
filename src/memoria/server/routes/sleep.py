"""Sleep Engine API endpoints."""

from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/v1/sleep", tags=["sleep"])


@router.get("/status")
async def sleep_status(request: Request):
    """Get sleep engine status."""
    engine = request.app.state.sleep_engine
    return {
        "state": engine.state,
        "idle_seconds": engine.idle_seconds,
        "threshold_seconds": engine.inactivity_threshold,
        "checkpoint": engine._checkpoint,
    }


@router.post("/start")
async def sleep_start(request: Request):
    """Manually start sleep consolidation."""
    engine = request.app.state.sleep_engine
    return engine.start(force=True)


@router.post("/stop")
async def sleep_stop(request: Request):
    """Stop sleep consolidation."""
    engine = request.app.state.sleep_engine
    return engine.stop()
