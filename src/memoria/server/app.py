"""FastAPI application factory."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from memoria.config import MemoriaConfig
from memoria.storage.sqlite import MemoriaDB
from memoria.storage.chroma import MemoriaChroma
from memoria.storage.embeddings import MemoriaEmbedding
from memoria.engine.ingest import IngestEngine
from memoria.engine.recall import RecallEngine
from memoria.server.routes import ingest, recall, status


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    config = app.state.config
    app.state.db = MemoriaDB(config.sqlite_path)
    app.state.embedder = MemoriaEmbedding(cache_dir=config.embedding_cache_dir)
    app.state.chroma = MemoriaChroma(config.chroma_path, app.state.embedder)
    app.state.ingest_engine = IngestEngine(
        db=app.state.db,
        chroma=app.state.chroma,
        embedder=app.state.embedder,
    )
    app.state.recall_engine = RecallEngine(
        db=app.state.db,
        chroma=app.state.chroma,
        embedder=app.state.embedder,
    )
    yield


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

    app.include_router(ingest.router)
    app.include_router(recall.router)
    app.include_router(status.router)

    return app
