# Roadmap

This is a solo, dogfooded project. No quarter labels, no fixed dates.
A feature appears here when there is a real spec or working code, not
when there is a hope.

## Released — v0.2.0 (2026-05-24)

Memory Intelligence Core, Benchmark Suite, OpenWebUI / OpenCode
integration, Quality Hardening. Full notes in
[CHANGELOG.md](CHANGELOG.md).

## Current — v0.3 (Trust / Security / Privacy)

Spec: [`v0.3 publication-grade Trust / Security / Privacy design`](docs/superpowers/specs/2026-05-26-v0.3-publication-trust-security-privacy-design.md).

The v0.3 **P0 ("Muss haben")** set from the spec:

- **Single API Key Auth** — `X-Mnemlet-Key` protection for REST and MCP
  when `MNEMLET_API_KEY` or `[auth].api_key` is configured.
- **Secret Guard** — block, warn, or allow configured write-path
  secret-like content by namespace policy.
- **Audit Log** — sanitized trail for auth, write, review, policy, and
  security-relevant actions.
- **Startup Security Checks** — warn when configuration is unsafe, such
  as non-local binds without a key.

The same spec also lists **P1 ("Soll haben")** features. Namespace
Policies, Explain+ trust blocks, protected Forget confirmation,
Secret Guard action policy, and Backup / Restore are now part of the
v0.3 release surface. Publish and PyPI language remains gated until
final release approval.

## Later — open questions, not promises

There is no committed roadmap after v0.3. Candidates that already have
a spec on disk:

- **Trust/Security/Privacy P2** — per-agent API keys, custom secret
  patterns, selective export, namespace soft-enforcement. See the same
  v0.3 spec.

Whether any of these ship depends on real use, real bugs, and real
need — not on a published date.
