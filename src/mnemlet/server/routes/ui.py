"""Read-only web dashboard shell served under /ui.

The dashboard is a single self-contained ``index.html`` (Alpine.js + Tailwind
from CDN). All four views are client-rendered, so every ``/ui`` path returns the
same shell and the browser routes on ``location.pathname``. Data is fetched from
the authenticated ``/api/v1`` endpoints; the shell itself carries no vault data
and is therefore exempt from API-key auth (see ``require_api_key``).
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, HTMLResponse, Response


router = APIRouter(tags=["ui"])

_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
_INDEX_FILE = _STATIC_DIR / "index.html"
_CACHE_HEADERS = {"Cache-Control": "public, max-age=3600"}


def _serve_index() -> Response:
    """Return the dashboard shell, cached for one hour."""
    if not _INDEX_FILE.exists():
        return HTMLResponse(
            "<h1>Mnémlet dashboard is not installed</h1>",
            status_code=500,
        )
    return FileResponse(_INDEX_FILE, media_type="text/html", headers=_CACHE_HEADERS)


@router.get("/ui")
async def ui_root() -> Response:
    """Serve the dashboard at the bare /ui path."""
    return _serve_index()


@router.get("/ui/{full_path:path}")
async def ui_catch_all(full_path: str) -> Response:
    """Serve the same shell for every client-routed dashboard path."""
    return _serve_index()
