# Security Policy

## Current State (v0.3+ Trust / Security / Privacy)

Mnémlet is local-first infrastructure. It binds to `127.0.0.1` by default and is designed to run near your AI agents on hardware you control.

Do not expose Mnémlet directly to the public internet. If you need remote access, put it behind your own trusted network boundary such as SSH, WireGuard, Tailscale, or a reverse proxy you already operate securely.

## Recommended Auth Mode

Generate one API key and run the server with that key configured:

```bash
mnemlet auth generate-key
export MNEMLET_API_KEY="mnemlet_..."
mnemlet serve
```

REST and MCP clients then send the key with `X-Mnemlet-Key`. Development mode can run without a key when bound to localhost, but that mode is only for trusted local use.

## Secret Guard

Secret Guard scans write-path content for common secret-like values such as API keys, bearer tokens, and password assignments. Namespace policy can block, warn, or allow matching writes.

Limitations:

- Regex scanning is a safety net, not a data-loss-prevention system.
- It can miss unusual or encoded secrets.
- It can flag harmless test strings.
- It does not encrypt existing vault or database content.

## Audit Log

Mnémlet records sanitized audit events for relevant REST and MCP actions, including auth denials, review actions, Secret Guard outcomes, policy changes, and audit reads. The log is intended for local troubleshooting and trust review. It avoids storing raw secret material, but it is not a tamper-proof security ledger.

## Still Out Of Scope

- Encryption at rest for the SQLite database and Markdown vault.
- Multi-user auth, per-agent RBAC, or tenant isolation.
- Built-in TLS termination.
- Public internet hardening.

Namespaces are organizational trust boundaries. If you need hard isolation between agents, run separate Mnémlet instances with separate data directories and ports.

## Responsible Disclosure

Found a security issue? Please report it privately by opening a GitHub issue titled `[SECURITY]` with a concise description and reproduction notes, or contact the maintainer through the private channel listed on the project profile if available. Do not disclose publicly until the issue is resolved.

## Dependencies

Mnémlet relies on:

- **ChromaDB** for vector storage.
- **SQLite** for metadata, FTS5, and audit storage.
- **onnxruntime** for local embeddings.
- **FastAPI/uvicorn** for the HTTP server.

Dependencies are pinned in `pyproject.toml`; critical CVEs should be treated as security bugs.
