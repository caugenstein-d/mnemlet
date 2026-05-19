# 🧠 Mnémlet

**Mnémlet is for people who don't want Mem0.** Not because Mem0 is bad software — it's excellent. But because you want your AI's memory to live on your own hardware, not someone else's cloud. You want a system that forgets what doesn't matter instead of hoarding everything forever. You want to open a file on disk and see what your agent actually knows about you. You want zero API bills and full control.

This is a **values** choice, not a feature checklist. If that resonates, welcome.

Built for [r/selfhosted](https://reddit.com/r/selfhosted) and [r/LocalLLaMA](https://reddit.com/r/LocalLLaMA) — people running AI on Pis, homelabs, old laptops, and local servers.

---

## What Mnémlet Does

Mnémlet is a self-hosted memory engine for AI agents. It learns what matters, forgets the rest, and consolidates knowledge while you sleep — all on hardware you control.

- 🧠 **Exponential decay + interaction-weighting** — Memories you recall and update stay sharp. What you ignore fades. No infinite hoarding.
- 😴 **Sleep Engine** — Nightly consolidation runs while you're away: deduplicate, rescore stale memories, cluster related knowledge, and generate a morning briefing. Like your brain during REM sleep.
- 🔌 **MCP-native with 8 tools** — `mnemlet_ingest`, `mnemlet_recall`, `mnemlet_search`, `mnemlet_status`, `mnemlet_namespaces`, `mnemlet_update`, `mnemlet_decay_config`, `mnemlet_export`. Works with OpenWebUI, OpenClaw, Claude Code, Cursor, or any MCP client.
- 📂 **Inspectable Markdown vault** — Every memory as a `.md` file with YAML frontmatter. Open in Obsidian. `grep` it. `git` it. No black box database lock-in.
- 🤖 **Optional local LLM** — Plug in Gemma3:4b via Ollama. Runs CPU-only on a Pi. Enhances sleep consolidation (contradiction detection, summarization).
- 🔍 **Hybrid search** — BM25 (SQLite FTS5) + vector similarity (ChromaDB). Both local, both free.
- 🥧 **Pi-ready** — 450 MB RAM baseline, ~4 GB with LLM. Runs on a Raspberry Pi 5 (16 GB recommended for the full stack).
- 💰 **Zero API costs** — Local ONNX embeddings (all-MiniLM-L6-v2). No OpenAI key, no cloud embedding service, no per-call charges. SearXNG optionally self-hosted for web enrichment.
- 🐍 **Python SDK, REST API, CLI** — `pip install mnemlet` then `mnemlet serve`.

---

## Honest Comparison

No checkmark bingo. Here's where Mnémlet shines, and where it doesn't.

| | Mnémlet | Mem0 | MemPalace | Engram (Go) | NeoCortex |
|---|---|---|---|---|---|
| **Self-hosted** | ✅ | ⚠️ (platform) | ✅ | ✅ | ❌ (API-only) |
| **Decay / Forgetting** | ✅ (deep) | ❌ | ❌ | ❌ | ✅ |
| **Sleep / Consolidation** | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Local LLM support** | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Vector search** | ✅ | ✅ | ✅ | ❌ (FTS5 only) | ✅ |
| **Inspectable vault** | ✅ (Markdown) | ❌ | ❌ | ⚠️ (beta) | ❌ |
| **TUI Dashboard** | ❌ | ❌ | ❌ | ✅ | ❌ |
| **Cloud sync** | ❌ | ✅ | ❌ | ✅ | ✅ |
| **MCP tools** | 8 | ~10 | 29 | 19 | ❌ (API) |
| **Language** | Python | Python | Python | Go | HTTP API |
| **License** | MIT | Apache 2.0 | MIT | MIT | MIT |
| **GitHub stars** | 0 | 48k | 52k | 3.6k | 193 |
| **Pi-friendly RAM** | ✅ (450 MB) | ❌ | ✅ | ✅ | ❌ |

If your priority is cloud sync, a polished dashboard, or an ecosystem with 50k stars — use Mem0 or MemPalace. They're great at those things.

If your priority is **local-first, brain-inspired forgetting, sleep consolidation, and running on hardware you own** — that's the gap Mnémlet fills.

---

## Quickstart

### Install

```bash
pip install mnemlet
```

### Start the server

```bash
mnemlet serve
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
from mnemlet.client import MnemletClient

c = MnemletClient()
c.ingest("Hello world")
results = c.recall("Hello")
print(results)
```

### Connect your agents

Add to any MCP client config:

```json
{"mcpServers": {"mnemlet": {"url": "http://localhost:4050/mcp"}}}
```

---

## How It Works

### The Brain Model

Every memory has a `retention_score` (0.0–1.0) that follows exponential decay:

```
score(t) = score₀ × e^(-λ × t)
```

| Memory type | λ value | Half-life |
|---|---|---|
| Preferences / identity | 0.001 | ~2 years |
| Project knowledge | 0.01 | ~69 days |
| Daily chat context | 0.05 | ~14 days |
| Transient / ephemeral | 0.5 | ~1.4 days |

Interactions boost retention: recall +0.15, update +0.20, create +0.10, reference +0.08.

When scores fall below configurable thresholds, memories move to cold storage or get purged. What you use stays sharp. What you ignore fades.

### The Sleep Engine

After 2 hours of inactivity, Mnémlet enters consolidation. Tasks run sequentially, locally, with zero API costs:

1. **Dedup** — Merge near-duplicate memories created today
2. **Rescore** — Apply time-decay and purge stale memories below threshold
3. **Cluster** — Group semantically similar memories by namespace
4. **Briefing** — Generate a morning context summary for the next session

You can trigger sleep manually via `/api/v1/sleep/start` or check status via `/api/v1/sleep/status`.

### Inspectable Vault

```
~/.mnemlet/vault/
  preferences/
    2026-05/
      a1b2c3d4.md          ← Open in Obsidian!
  projects/
    mirofish/
      2026-05/
        e5f6g7h8.md
```

Every memory is a Markdown file with YAML frontmatter. You can read, edit, version-control, or delete memories with any text editor. No black box.

---

## API Reference

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/health` | GET | Health check |
| `/api/v1/status` | GET | Memory counts, storage stats, decay info |
| `/api/v1/ingest` | POST | Store a memory |
| `/api/v1/recall` | POST | Retrieve relevant memories |
| `/api/v1/decay/run` | POST | Manual decay run + purge |
| `/api/v1/namespaces/{ns}/decay` | GET/PUT | Per-namespace decay configuration |
| `/api/v1/vault` | GET | Vault path and file count |
| `/api/v1/sleep/status` | GET | Sleep engine state |
| `/api/v1/sleep/start` | POST | Start sleep cycle manually |
| `/api/v1/sleep/stop` | POST | Stop sleep cycle gracefully |
| `/mcp` | SSE | MCP server endpoint (8 tools) |

---

## Configuration

```toml
# mnemlet.toml
[server]
host = "127.0.0.1"
port = 4050

[storage]
data_dir = "~/.mnemlet"

[llm]
enabled = false           # Enable for Gemma3:4b via Ollama
provider = "ollama"
model = "gemma3:4b"

[search]
enabled = false           # Enable for SearXNG web enrichment
provider = "searxng"
base_url = "http://localhost:8888"
```

---

## Raspberry Pi

Mnémlet runs on a Raspberry Pi 5. The 16 GB model is recommended if you're running Ollama alongside it.

| Mode | RAM usage |
|---|---|
| Base (no LLM, no search) | ~450 MB |
| + SearXNG | ~650 MB |
| + Gemma3:4b (Ollama) | ~4 GB total |

This is the actual stack I run: Mnémlet + OpenWebUI + OpenCode + OpenClaw on two Pi 5s in my homelab.

---

## Why I Built This

I wanted my AI agents to remember context between sessions — my preferences, project details, ongoing conversations. Existing options required cloud accounts, per-request pricing, or opaque storage. I couldn't open a database and see what the system actually knew about me.

So I built something that runs on hardware I own, stores memories as files I can read, and respects the fact that not everything is worth remembering forever.

---

## What Mnémlet Is NOT

- **Not a Mem0 competitor for enterprise teams.** This is a solo tool, built for solo setups. It has no auth layers, no multi-tenancy, no cloud offering, and no VC funding behind it.
- **Not a cloud service.** There is no `app.mnemlet.ai`. There never will be. If you want managed hosting, look at Mem0.
- **Not a production database.** It's AA-battery-grade infrastructure — simple, local, sufficient for one person's context. Don't use it to store customer PII or medical records.
- **Not a replacement for your notes app.** The Markdown vault is inspectable, but it's not designed for manual note-taking. Use Obsidian for that. Use Mnémlet for agent memory.

---

## Maintainer Statement

I maintain this because I use it daily. It powers my homelab AI stack — OpenWebUI, OpenCode, and OpenClaw on two Raspberry Pi 5s. It lives as long as I use it. Bug reports and pull requests are welcome, but set expectations accordingly: this is a solo-dev, dogfooded project.

---

## Security

By default, Mnémlet binds to `127.0.0.1` only. There is no authentication layer yet — treat it as a local service. Do not expose it to the public internet. Production auth is planned for v0.3.

---

## License

[MIT](LICENSE)

---

*Built with 🧠 on a Raspberry Pi.*
