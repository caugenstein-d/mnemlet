"""Sleep Engine control routes."""

from fastapi import APIRouter, Request


router = APIRouter(prefix="/api/v1/sleep", tags=["sleep"])


@router.get("/status")
async def sleep_status(request: Request) -> dict:
    """Get sleep engine status."""
    engine = request.app.state.sleep_engine
    return engine.status()


@router.post("/start")
async def sleep_start(request: Request) -> dict:
    """Manually start sleep consolidation."""
    engine = request.app.state.sleep_engine
    return engine.start(force=True)


@router.post("/stop")
async def sleep_stop(request: Request) -> dict:
    """Stop sleep consolidation."""
    engine = request.app.state.sleep_engine
    return engine.stop()
