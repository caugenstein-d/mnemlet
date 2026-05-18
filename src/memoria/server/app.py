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
from memoria.server.routes import decay, ingest, recall, status
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

    mcp = create_mcp_server(app.state)
    app.mount("/mcp", mcp.streamable_http_app())

    async def decay_loop():
        """Run decay processing every 6 hours."""
        while True:
            await asyncio.sleep(6 * 3600)  # 6 hours
            try:
                decay = DecayEngine(app.state.db)
                result = decay.decay_all_active(limit=500)
                print(f"[decay] processed={result['processed']} decayed={result['decayed']} "
                      f"cold={result['moved_to_cold']} deleted={result['hard_deleted']}")
            except Exception as e:
                print(f"[decay] error: {e}")

    task = asyncio.create_task(decay_loop())
    yield
    task.cancel()
    try:
        await task
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

    app.include_router(decay.router)
    app.include_router(ingest.router)
    app.include_router(recall.router)
    app.include_router(status.router)

    return app
