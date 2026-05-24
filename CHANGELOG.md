# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project
uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] — 2026-05-24

### Added
- **Memory Intelligence Core**: intelligence memory schema, status-aware
  recall with provenance, memory classifier policies, and supersession
  pipeline (with hardened metadata merge and detector confidence).
- **Context Pack API** with abstention reasons; MCP context tool aligned
  with the REST contract.
- **Memory review commands** — `forget`, `replace`, `confirm`, `explain` —
  with input validation.
- **Benchmark suite**: dataset model with strict validation, runner with
  canonical metric aliases, JSON/MD/CSV reports CLI, adapter checks, and
  opt-in live OpenWebUI / OpenCode checks.
- **Quality Benchmark**: dataset and runner with per-scenario isolation,
  summary metrics, missing-memory assertions, and a repo-local OpenWebUI
  filter fixture for hermetic adapter tests.
- OpenWebUI / OpenCode integration design and MCP server lifespan init.

### Changed
- Benchmark CLI separates Quality from Quick/Full argument groups; Quality
  no longer silently ignores retrieval/live flags or double-runs adapter
  checks.
- Recall no longer starves under status filters — pre-filter pool widened.

### Fixed
- Sleep engine no longer consolidates repeatedly, marks failed epochs as
  complete, or reuses a stale worker; retry test stabilized.
- REST review/explain endpoints return HTTP 404 for missing memories
  instead of HTTP 200 with an `error` field.
- Quality benchmark `false_positive_rate` is `0.0` when a run has no
  abstention assertions.
- QualityRunner resets storage and logical state between scenarios so
  facts from one scenario cannot leak into the next.
- QualityRunner reports a structured `missing_memory` assertion instead of
  crashing with `TypeError` when a logical memory id has no backing row.

## [0.1.0] — initial release

Foundational Mnémlet: SQLite/FTS5 + ChromaDB hybrid recall, FastAPI
server, decay engine with per-namespace configuration, purge with cold
storage, MCP server (8 tools), Python SDK, Sleep Engine, inspectable
Markdown vault, optional Ollama and SearXNG backends, local ONNX
embeddings, landing page, and asciinema demo.
