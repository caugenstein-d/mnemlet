"""FastAPI application factory."""

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from memoria.config import MemoriaConfig
from memoria.storage.sqlite import MemoriaDB
from memoria.storage.chroma import MemoriaChroma
from memoria.storage.embeddings import MemoriaEmbedding
from memoria.storage.vault import VaultWriter
from memoria.engine.ingest import IngestEngine
from memoria.engine.recall import RecallEngine
from memoria.engine.decay import DecayEngine
from memoria.engine.sleep import SleepEngine
from memoria.server.routes import decay, ingest, recall, sleep, status
from memoria.server.mcp_server import create_mcp_server


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    config = app.state.config
    app.state.db = MemoriaDB(config.sqlite_path)
    app.state.embedder = MemoriaEmbedding(cache_dir=config.embedding_cache_dir)
    app.state.chroma = MemoriaChroma(config.chroma_path, app.state.embedder)
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

    mcp = create_mcp_server(app.state)
    app.mount("/mcp", mcp.streamable_http_app())

    async def decay_loop():
        """Run decay processing every 6 hours."""
        while True:
            await asyncio.sleep(6 * 3600)  # 6 hours
            try:
                result = decay_engine.decay_all_active(limit=500)
                print(f"[decay] processed={result['processed']} decayed={result['decayed']} "
                      f"cold={result['moved_to_cold']} deleted={result['hard_deleted']}")
            except Exception as e:
                print(f"[decay] error: {e}")

    async def sleep_monitor():
        """Check inactivity and trigger sleep phase."""
        while True:
            await asyncio.sleep(300)  # Check every 5 minutes
            if app.state.sleep_engine.should_sleep():
                print("[sleep] Inactivity threshold reached, starting consolidation...")
                app.state.sleep_engine.start()

    task = asyncio.create_task(decay_loop())
    sleep_task = asyncio.create_task(sleep_monitor())
    yield
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


def create_app(config: MemoriaConfig = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    if config is None:
        config = MemoriaConfig()

    app = FastAPI(
        title="Memoria",
        description="Self-hosted, brain-inspired memory engine for AI agents.",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.config = config

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def track_activity(request, call_next):
        """Bump sleep engine activity on every API call."""
        if hasattr(request.app.state, 'sleep_engine'):
            request.app.state.sleep_engine.bump_activity()
        response = await call_next(request)
        return response

    app.include_router(decay.router)
    app.include_router(ingest.router)
    app.include_router(recall.router)
    app.include_router(sleep.router)
    app.include_router(status.router)

    return app
