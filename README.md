# 🧠 Engram

**The self-hosted memory engine that learns what matters, forgets the rest — and thinks while you sleep.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)

---

## Why Engram?

Your AI agents forget everything between sessions. Existing memory systems either:
- Store everything forever (growing unboundedly)
- Cost money per API call (cloud-dependent)
- Only work with one agent (fragmented)

**Engram is different.** It's a self-hosted, brain-inspired memory engine that:

- 🧠 **Forgets intelligently** — Exponential time-decay + interaction-weighting. What you use stays sharp. What you ignore fades.
- 🌐 **Works with all your agents** — MCP-native. OpenWebUI, OpenClaw, Claude Code, Cursor, any MCP client.
- 😴 **Thinks while you sleep** — Night consolidation: deduplication, clustering, contradiction detection, morning briefing.
- 📂 **Inspectable vault** — Every memory as a Markdown file. You see exactly what the system knows.
- 🥧 **Runs on a Pi** — Zero API costs. Local embeddings. ~450MB RAM base, 4GB with optional local LLM.
- 🔌 **8 MCP tools** — Ingest, recall, search, status, namespaces, update, decay config, export.

---

## Quickstart

### Install

```bash
pip install engram
```

### Start the server

```bash
engram serve
# → http://localhost:4050
```

### Store your first memory

```bash
curl -X POST http://localhost:4050/api/v1/ingest \
  -H 'Content-Type: application/json' \
  -d '{"content":"I prefer dark mode in all editors","namespace":"preferences","importance":0.9}'
```

### Retrieve it

```bash
curl -X POST http://localhost:4050/api/v1/recall \
  -H 'Content-Type: application/json' \
  -d '{"query":"editor preferences","namespace":"preferences"}'
```

### Python SDK

```python
from engram.client import EngramClient

c = EngramClient()
c.ingest("Hello world")
results = c.recall("Hello")
print(results)
```

### Connect your agents

Add to any MCP client config:

```json
{"mcpServers": {"engram": {"url": "http://localhost:4050/mcp"}}}
```

---

## How It Works

### The Brain Model

Every memory has a `retention_score` (0.0–1.0) that follows exponential decay:

```
score(t) = score₀ × e^(-λ × t)
```

- **Preferences** decay very slowly (λ=0.001, ~2 year half-life)
- **Daily chats** decay faster (λ=0.05, ~14 day half-life)
- **Temporary** data decays rapidly (λ=0.5, ~1.4 day half-life)

Interactions boost scores: recall +0.15, update +0.20, create +0.10, reference +0.08.

### The Sleep Engine

When no API calls occur for 2+ hours, Engram enters consolidation:

1. **Dedup** — Merge near-duplicate memories from today
2. **Rescore** — Apply time-decay and purge stale memories
3. **Cluster** — Group semantically similar memories
4. **Briefing** — Generate morning context for the next session

All tasks run sequentially, locally, with zero API costs.

### Inspectable Vault

```
~/.engram/vault/
  preferences/
    2026-05/
      a1b2c3d4.md      ← Open in Obsidian!
  projects/
    mirofish/
      2026-05/
        e5f6g7h8.md
```

Every memory is a Markdown file with YAML frontmatter. Full transparency.

---

## API

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/health` | GET | Health check |
| `/api/v1/status` | GET | Memory counts & stats |
| `/api/v1/ingest` | POST | Store a memory |
| `/api/v1/recall` | POST | Retrieve memories |
| `/api/v1/decay/run` | POST | Manual decay + purge |
| `/api/v1/namespaces/{ns}/decay` | GET/PUT | Per-namespace decay config |
| `/api/v1/vault` | GET | Vault path & file count |
| `/api/v1/sleep/status` | GET | Sleep engine state |
| `/api/v1/sleep/start` | POST | Start sleep manually |
| `/api/v1/sleep/stop` | POST | Stop sleep gracefully |
| `/mcp` | SSE | MCP server (8 tools) |

---

## Configuration

```toml
# engram.toml
[server]
host = "127.0.0.1"
port = 4050

[storage]
data_dir = "~/.engram"

[llm]
enabled = false           # Enable for Gemma 4 E2B via Ollama
provider = "ollama"
model = "gemma4-e2b:q4_0"

[search]
enabled = false           # Enable for SearXNG web enrichment
provider = "searxng"
base_url = "http://localhost:8888"
```

---

## Raspberry Pi

Engram runs on a Raspberry Pi 5 (16GB recommended for full feature set):

| Mode | RAM |
|---|---|
| Base (no LLM, no search) | ~450 MB |
| + SearXNG | ~650 MB |
| + Gemma 4 E2B (Ollama) | ~4 GB total |

---

## What Makes Engram Different

| | MemPalace | Mem0 | NeoCortex | Dakera | **Engram** |
|---|---|---|---|---|---|
| Self-hosted | ✅ | ⚠️ | ❌ | ✅ | ✅ |
| Decay | ❌ | ❌ | ✅ | ✅ | ✅ **deep** |
| Sleep/Consolidation | ❌ | ❌ | ❌ | ❌ | ✅ |
| Cross-Agent MCP | ❌ | ❌ | ❌ | ❌ | ✅ |
| Inspectable Vault | ❌ | ❌ | ❌ | ❌ | ✅ |
| Zero API Costs | ✅ | ❌ | ❌ | ✅ | ✅ |
| Pi-ready | ✅ | ❌ | ❌ | ⚠️ | ✅ |

---

## License

MIT — see [LICENSE](LICENSE).

---

*Built with 🧠 on a Raspberry Pi.*
