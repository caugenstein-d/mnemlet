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
from mnemlet.security.audit import AuditEvent, AuditResult
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
from mnemlet.server.routes import audit, context, decay, explain, ingest, memories, recall, review, sleep, status, ui
from mnemlet.server.mcp_server import create_mcp_server


def _get_mcp_session_manager(mcp_app: Any) -> Any:
    """Locate FastMCP's streamable HTTP session manager from its route endpoint."""
    for route in mcp_app.routes:
        endpoint = getattr(route, "endpoint", None)
        session_manager = getattr(endpoint, "session_manager", None)
        if session_manager is not None:
            return session_manager
    raise RuntimeError("FastMCP session manager route endpoint not found")


def _audit_action_from_request(request: Request) -> str:
    """Map a REST request path to a coarse audit action."""
    path = request.url.path
    if path.endswith("/ingest") or path.endswith("/remember"):
        return "ingest"
    if "/recall" in path or "/context" in path:
        return "recall"
    if "/explain" in path:
        return "explain"
    if "/forget" in path:
        return "forget"
    if "/replace" in path:
        return "replace"
    if "/confirm" in path:
        return "confirm"
    if "/audit" in path:
        return "audit"
    return "request"


def _audit_namespace_from_request(request: Request) -> str:
    """Derive a sanitized namespace value without reading request bodies."""
    namespace = request.query_params.get("namespace")
    if namespace:
        return namespace
    parts = request.url.path.strip("/").split("/")
    if "namespaces" in parts:
        index = parts.index("namespaces") + 1
        if index < len(parts):
            return parts[index]
    return "default"


def _record_request_audit(request: Request, result: AuditResult, status_code: int | None = None) -> None:
    """Record sanitized audit data when the database is available."""
    db = getattr(request.app.state, "db", None)
    if db is None:
        return
    decision = getattr(request.state, "auth_decision", None)
    details: dict[str, object] = {
        "method": request.method,
        "path": request.url.path,
    }
    if status_code is not None:
        details["status_code"] = status_code
    reason = getattr(decision, "reason", None)
    if reason:
        details["reason"] = reason
    db.record_audit(
        AuditEvent(
            action=_audit_action_from_request(request),
            namespace=_audit_namespace_from_request(request),
            caller="rest",
            caller_identity=getattr(decision, "caller_identity", None),
            result=result,
            details=details,
        )
    )


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

    # Optional LLM backend (off by default). Construction is lazy and makes no
    # network calls, so this is safe even when Ollama is unreachable.
    app.state.llm = None
    app.state.extraction_pipeline = None
    if getattr(config, "llm_enabled", False):
        from mnemlet.engine.llm import LLMBackend

        app.state.llm = LLMBackend(base_url=config.llm_base_url, model=config.llm_model)

        # v0.4 intelligent extraction pipeline (requires the LLM backend).
        if getattr(config, "extraction_enabled", False):
            from mnemlet.intelligence.pipeline import ExtractionPipeline

            app.state.extraction_pipeline = ExtractionPipeline(
                ingest_engine=app.state.ingest_engine,
                llm_client=app.state.llm,
                extract_memories=config.extract_memories,
                summarize_conversations=config.summarize_conversations,
                inactivity_threshold_minutes=config.inactivity_threshold_minutes,
                max_messages=config.max_buffer_messages,
            )

    # Create sleep engine (LLM, when present, powers richer morning briefings)
    decay_engine = DecayEngine(app.state.db)
    app.state.sleep_engine = SleepEngine(
        db=app.state.db,
        chroma=app.state.chroma,
        embedder=app.state.embedder,
        vault=app.state.vault,
        decay_engine=decay_engine,
        llm=app.state.llm,
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
            # Tear down the extraction pipeline without flushing (a slow LLM
            # flush must not block shutdown) and close the LLM HTTP client.
            pipeline = getattr(app.state, "extraction_pipeline", None)
            if pipeline is not None:
                pipeline.shutdown()
            llm = getattr(app.state, "llm", None)
            if llm is not None and hasattr(llm, "close"):
                llm.close()


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
    async def track_activity(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Bump sleep engine activity on every API call.

        The read-only dashboard sends ``X-Mnemlet-UI: 1`` on its polls; that
        traffic must not keep the engine awake, or a dashboard left open would
        block nightly consolidation forever.
        """
        is_ui_poll = request.headers.get("x-mnemlet-ui") == "1"
        if hasattr(request.app.state, 'sleep_engine') and not is_ui_poll:
            request.app.state.sleep_engine.bump_activity()
        response = await call_next(request)
        return response

    @app.middleware("http")
    async def audit_rest_request(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Record one sanitized audit event per authenticated REST request."""
        response = await call_next(request)
        if request.url.path.startswith("/api/v1"):
            audit_result = getattr(request.state, "audit_result", "success")
            _record_request_audit(request, audit_result, response.status_code)
        return response

    # Decorator middleware executes in reverse declaration order; keep auth last
    # so rejected requests cannot bump sleep activity or request audit middleware.
    @app.middleware("http")
    async def require_api_key(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Require API key when configured."""
        # The dashboard shell carries no vault data and must load before the
        # user can enter a key, so /ui is served without auth. All data still
        # flows through the protected /api/v1 endpoints.
        path = request.url.path
        if path == "/ui" or path.startswith("/ui/"):
            return await call_next(request)
        configured_key = getattr(request.app.state.config, "api_key", None)
        provided_key = extract_request_key(dict(request.headers))
        decision = validate_api_key(configured_key, provided_key)
        request.state.auth_decision = decision
        if not decision.allowed:
            _record_request_audit(request, "denied", 401)
            return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
        return await call_next(request)

    app.include_router(audit.router)
    app.include_router(context.router)
    app.include_router(decay.router)
    app.include_router(ingest.router)
    app.include_router(memories.router)
    app.include_router(recall.router)
    app.include_router(sleep.router)
    app.include_router(status.router)
    app.include_router(explain.router)
    app.include_router(review.router)
    app.include_router(ui.router)

    return app
