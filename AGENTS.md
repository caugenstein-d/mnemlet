# Memoria — Agent Instructions

Project: Memoria
Phase: 1 — Core Engine
Language: Python 3.12+
Testing: pytest with TDD

**Key Rules:**
- Write the failing test FIRST, then the implementation.
- Every function needs type annotations.
- Every module gets docstrings.
- Commit after every passing test.

**Architecture:**
- `storage/` — data layer (SQLite, ChromaDB, embeddings)
- `engine/` — business logic (ingest, recall, decay)
- `server/` — HTTP layer (FastAPI, routes, MCP)
- `client/` — Python SDK (future phase)
