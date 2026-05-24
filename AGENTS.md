# Mnemlet — Agent Instructions

Project: Mnemlet
Phase: 2 — Memory Intelligence + Benchmark Suite (v0.2.0 released 2026-05-24, v0.3 = Trust/Security/Privacy)
Language: Python 3.12+
Testing: pytest with TDD

**Key Rules:**
- Write the failing test FIRST, then the implementation.
- Every function needs type annotations.
- Every module gets docstrings.
- Commit after every passing test.

**Architecture:**
- `storage/` — data layer (SQLite/FTS5, ChromaDB, ONNX embeddings, Markdown vault)
- `engine/` — business logic (ingest, recall, decay, sleep, llm)
- `intelligence/` — memory intelligence (classifier policies, supersession, review service, context packs, abstention, provenance)
- `benchmark/` — benchmark suite (datasets, runner, quality runner, adapters, live checks, reports)
- `server/` — HTTP layer (FastAPI routes, MCP server with 14 tools)
- `client/` — Python SDK
