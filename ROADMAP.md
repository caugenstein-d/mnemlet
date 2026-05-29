# Roadmap

This is a solo project built on conviction, not daily dogfooding of every feature.
No quarter labels, no fixed dates. A feature appears here when there is a real spec
or working code, not when there is a hope.

## Released — v0.2.0 (2026-05-24)

Memory Intelligence Core, Benchmark Suite, OpenWebUI / OpenCode
integration, Quality Hardening. Full notes in
[CHANGELOG.md](CHANGELOG.md).

## Released — v0.3.0 (2026-05-28)

Trust / Security / Privacy layer. Spec:
[`v0.3 publication-grade Trust / Security / Privacy design`](docs/superpowers/specs/2026-05-26-v0.3-publication-trust-security-privacy-design.md).

- **Single API Key Auth** — `X-Mnemlet-Key` protection for REST and MCP
  when `MNEMLET_API_KEY` or `[auth].api_key` is configured.
- **Secret Guard** — block, warn, or allow configured write-path
  secret-like content by namespace policy.
- **Audit Log** — sanitized trail for auth, write, review, policy, and
  security-relevant actions.
- **Startup Security Checks** — warn when configuration is unsafe, such
  as non-local binds without a key.
- **Namespace Policies** — per-namespace trust policies for Secret Guard,
  confirmation requirements, and access control.
- **Explain+ Trust Blocks** — provenance metadata showing why a memory
  exists and whether it is active, superseded, forgotten, or confirmed.
- **Backup / Restore** — encrypted backups with namespace filtering.

## Released — v0.4.0 (2026-05-29)

Intelligent Memory Extraction. Spec:
[`v0.4 intelligent extraction plan`](docs/superpowers/plans/2026-05-28-v0.4-intelligent-memory-extraction.md).

- **LLM-powered conversation extraction** — automatically turns chats into
  structured memories (preferences, facts, decisions, context).
- **Platform adapters** — OpenWebUI, Claude Code, OpenCode, OpenClaw, Cursor,
  Claude Desktop, and generic MCP clients.
- **Conversation buffer** — collects messages per session, triggers extraction
  after 10 minutes of inactivity.
- **Morning briefings** — LLM-generated summaries of your recent work, not
  just lists of top memories.
- **Web dashboard** — read-only UI at `/ui` showing memories, audit log,
  and system status.

**Note:** Core features (decay, sleep, vault, auth) run on a Raspberry Pi.
LLM extraction needs more power — a beefy workstation, remote LLM host, or
cloud API.

## Later — open questions, not promises

There is no committed roadmap after v0.4. Candidates that already have
a spec on disk:

- **Trust/Security/Privacy P2** — per-agent API keys, custom secret
  patterns, selective export, namespace soft-enforcement. See the
  v0.3 spec.
- **Phase 2 platform adapters** — Windsurf, VS Code + GitHub Copilot, Cline.
- **Phase 3 community platforms** — Zed, Continue.dev, LibreChat.

Whether any of these ship depends on real use, real bugs, and real
need — not on a published date.
