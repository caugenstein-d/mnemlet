"""FastAPI application factory."""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AsyncExitStack, asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from mnemlet import __version__
from mnemlet.config import MnemletConfig
from mnemlet.security.auth import extract_request_key, validate_api_key
from mnemlet.security.startup_check import run_startup_security_checks
from mnemlet.storage.sqlite import MnemletDB
from mnemlet.storage.chroma import MnemletChroma
from mnemlet.storage.embeddings import MnemletEmbedding
from mnemlet.storage.vault import VaultWriter
from mnemlet.engine.ingest import IngestEngine
from mnemlet.engine.recall import RecallEngine
from mnemlet.engine.decay import DecayEngine
from mnemlet.engine.sleep import SleepEngine
from mnemlet.server.routes import context, decay, explain, ingest, recall, review, sleep, status
from mnemlet.server.mcp_server import create_mcp_server


def _get_mcp_session_manager(mcp_app: Any) -> Any:
    """Locate FastMCP's streamable HTTP session manager from its route endpoint."""
    for route in mcp_app.routes:
        endpoint = getattr(route, "endpoint", None)
        session_manager = getattr(endpoint, "session_manager", None)
        if session_manager is not None:
            return session_manager
    raise RuntimeError("FastMCP session manager route endpoint not found")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup and shutdown lifecycle."""
    config = app.state.config
    for warning in getattr(app.state, "security_warnings", []):
        print(f"[security] {warning.level}: {warning.message}")
    app.state.db = MnemletDB(config.sqlite_path)
    app.state.embedder = MnemletEmbedding(cache_dir=config.embedding_cache_dir)
    app.state.chroma = MnemletChroma(config.chroma_path, app.state.embedder)
    app.state.vault = VaultWriter(config.vault_path)
    app.state.ingest_engine = IngestEngine(
        db=app.state.db,
        chroma=app.state.chroma,
        embedder=app.state.embedder,
        vault=app.state.vault,
    )
    app.state.recall_engine = RecallEngine(
        db=app.state.db,
        chroma=app.state.chroma,
        embedder=app.state.embedder,
    )

    # Create sleep engine
    decay_engine = DecayEngine(app.state.db)
    app.state.sleep_engine = SleepEngine(
        db=app.state.db,
        chroma=app.state.chroma,
        embedder=app.state.embedder,
        vault=app.state.vault,
        decay_engine=decay_engine,
    )

    async def decay_loop() -> None:
        """Run decay processing every 6 hours."""
        while True:
            await asyncio.sleep(6 * 3600)  # 6 hours
            try:
                result = decay_engine.decay_all_active(limit=500)
                print(f"[decay] processed={result['processed']} decayed={result['decayed']} "
                      f"cold={result['moved_to_cold']} deleted={result['hard_deleted']}")
            except Exception as e:
                print(f"[decay] error: {e}")

    async def sleep_monitor() -> None:
        """Check inactivity and trigger sleep phase."""
        while True:
            await asyncio.sleep(300)  # Check every 5 minutes
            if app.state.sleep_engine.should_sleep():
                print("[sleep] Inactivity threshold reached, starting consolidation...")
                app.state.sleep_engine.start()

    async with AsyncExitStack() as stack:
        await stack.enter_async_context(
            app.state.mcp_app.router.lifespan_context(app.state.mcp_app)
        )
        task = asyncio.create_task(decay_loop())
        sleep_task = asyncio.create_task(sleep_monitor())
        try:
            yield
        finally:
            task.cancel()
            sleep_task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            try:
                await sleep_task
            except asyncio.CancelledError:
                pass


def create_app(config: MnemletConfig | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    if config is None:
        config = MnemletConfig()

    app = FastAPI(
        title="Mnemlet",
        description="Self-hosted, brain-inspired memory engine for AI agents.",
        version=__version__,
        lifespan=lifespan,
    )
    app.state.config = config
    app.state.security_warnings = run_startup_security_checks(config)
    mcp = create_mcp_server(app.state)
    mcp_app = mcp.streamable_http_app()
    app.state.mcp_app = mcp_app
    app.state.mcp_session_manager = _get_mcp_session_manager(mcp_app)
    app.mount("/mcp", mcp_app)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def require_api_key(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Require API key when configured."""
        configured_key = getattr(request.app.state.config, "api_key", None)
        provided_key = extract_request_key(dict(request.headers))
        decision = validate_api_key(configured_key, provided_key)
        request.state.auth_decision = decision
        if not decision.allowed:
            return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
        return await call_next(request)

    @app.middleware("http")
    async def track_activity(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Bump sleep engine activity on every API call."""
        if hasattr(request.app.state, 'sleep_engine'):
            request.app.state.sleep_engine.bump_activity()
        response = await call_next(request)
        return response

    app.include_router(context.router)
    app.include_router(decay.router)
    app.include_router(ingest.router)
    app.include_router(recall.router)
    app.include_router(sleep.router)
    app.include_router(status.router)
    app.include_router(explain.router)
    app.include_router(review.router)

    return app
