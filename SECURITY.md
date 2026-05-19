# Security Policy

## Current State (v0.1.0)

Mnémlet is **local-only infrastructure**. It binds to `127.0.0.1` by default and is designed to run on a trusted local network — typically the same machine as your AI agents (OpenWebUI, OpenCode, OpenClaw, etc.).

### What we have

- **Localhost binding**: Default bind is `127.0.0.1:4050`. The MCP endpoint at `/mcp` is only reachable locally.
- **No plaintext secrets on disk**: OAuth tokens and API keys are not stored by Mnémlet. It doesn't connect to third-party services unless you explicitly configure optional backends (Ollama, SearXNG).
- **OS-level file permissions**: The vault (`~/.mnemlet/vault/`) and database (`~/.mnemlet/mnemlet.db`) use standard Unix permissions. Set restrictive permissions if you run multi-user.

### What we do NOT have (yet)

- **No authentication**: The REST API and MCP endpoint have no auth layer. Anyone who can reach `localhost:4050` can read and write memories.
- **No encryption at rest**: The SQLite database and Markdown vault are stored unencrypted.
- **No rate limiting on the API**: A local process could flood the server.
- **No TLS**: Traffic between agents and Mnémlet is unencrypted (but it's on localhost).
- **No audit logging**: API calls are not logged beyond what the server prints to stdout.

### What this means

> Treat Mnémlet like a local database, not a public service. Do not expose it to the internet. Do not run it on a shared machine with untrusted users.

## Planned Improvements

| Feature | Target Version |
|---|---|
| API key authentication | v0.3 |
| Rate limiting | v0.3 |
| TLS support | v0.4 |
| Audit logging | v0.4 |
| Encryption at rest | later |

## Reporting

Found a security issue? Please report it privately by opening a GitHub issue with the title `[SECURITY]` and a description. Do not disclose publicly until resolved.

## Dependencies

Mnémlet relies on:
- **ChromaDB** (vector storage)
- **SQLite** (metadata and FTS5)
- **onnxruntime** (local embeddings)
- **FastAPI/uvicorn** (HTTP server)

All dependencies are pinned in `pyproject.toml`. We monitor for critical CVEs in these packages.

## MCP Security

The MCP server exposes 8 tools. In the current version, any MCP client connecting to `localhost:4050/mcp` has full access to all tools. There is no tool-level access control or per-agent permission model. This means:

- An agent with MCP access can read ANY namespace
- An agent with MCP access can write to ANY namespace
- An agent with MCP access can modify decay configurations

Namespace isolation is *organizational*, not *security*. If you need hard isolation between agents, run separate Mnémlet instances on different ports.
