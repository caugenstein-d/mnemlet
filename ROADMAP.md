# Roadmap

This is a solo, dogfooded project. No quarter labels, no fixed dates.
A feature appears here when there is a real spec or working code, not
when there is a hope.

## Released — v0.2.0 (2026-05-24)

Memory Intelligence Core, Benchmark Suite, OpenWebUI / OpenCode
integration, Quality Hardening. Full notes in
[CHANGELOG.md](CHANGELOG.md).

## Next — v0.3 (Trust / Security / Privacy)

Spec: [`trust-security-privacy-layer-design.md`](docs/superpowers/specs/2026-05-22-trust-security-privacy-layer-design.md).

The v0.3 **P0 ("Muss haben")** set from the spec, in priority order:

- **Single API Key Auth** — protect against accidental exposure on a
  homelab port-scan. No-auth is no-go beyond v0.2.
- **Secret Regex Guard** — refuse to ingest API keys, tokens, and
  passwords. Saves a human from themselves.
- **Audit Log** — full trail of who/what/why for every change.
  Foundation for the v0.3 "Why do you know this?" (Explain+) work.
- **Startup-Security-Check** — warn at startup when configuration is
  unsafe (`0.0.0.0` bind, missing key, world-readable data files).

The same spec also lists **P1 ("Soll haben")** features — Namespace
Policies, Explain+ (Trust-Erweiterung), Forget/Replace/Confirm trust
extensions, Backup / Restore — that build on the P0 set. Treat them as
v0.3-stretch, not v0.3-required.

## Later — open questions, not promises

There is no committed roadmap after v0.3. Candidates that already have
a spec on disk:

- **Trust/Security/Privacy P2** — per-agent API keys, custom secret
  patterns, selective export, namespace soft-enforcement. See the same
  v0.3 spec.

Whether any of these ship depends on real use, real bugs, and real
need — not on a published date.
