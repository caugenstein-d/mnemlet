# Contributing

Mnémlet is a solo, dogfooded project. Pull requests are welcome but
small. Big changes should start as an issue so we can agree on scope
before you write code.

## Before you open an issue or PR

- Check [ROADMAP.md](ROADMAP.md) — the feature you have in mind may
  already be planned for v0.3 or deliberately deferred.
- For bugs, use the [Bug report](https://github.com/christoph/mnemlet/issues/new?template=bug_report.yml) form.
- For features, use the [Feature request](https://github.com/christoph/mnemlet/issues/new?template=feature_request.yml) form.
- For security issues, **do not file a public issue** — follow [SECURITY.md](SECURITY.md).

## Local setup

```bash
git clone https://github.com/christoph/mnemlet.git
cd mnemlet
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
.venv/bin/pytest -q
```

The full suite should report `190 passed` (or higher) on a clean
checkout. If it does not, that is a bug — file it.

## Test rules

- Write the failing test FIRST, then the implementation. The repo
  follows TDD; see `AGENTS.md`.
- Use `.venv/bin/pytest`, never plain `pytest`, never `uv run pytest`.
  `uv` is not part of the developer dependencies.
- Every function gets a type annotation. Every module gets a docstring.
- No source-code change ships without a test that would have caught the
  regression.

## Commit style

The repo uses Conventional Commits. Single-line subjects, no body
unless the change really needs it, no `Co-Authored-By` trailer.

Prefixes in active use:

- `feat:` new user-facing capability
- `fix:` user-visible bug fix
- `docs:` documentation only
- `test:` tests only
- `chore:` build, CI, tooling, repo housekeeping
- `release:` version bump and CHANGELOG entry

One commit per logical change. Plan documents land in their own `docs:`
commit before the implementing `feat:` / `fix:` commits.

## Running benchmarks

Two benchmarks must stay green for any PR that touches retrieval,
intelligence, or quality semantics:

```bash
.venv/bin/mnemlet benchmark quick --dataset public \
  --output benchmark-results/latest --format json,md,csv --include-adapters

.venv/bin/mnemlet benchmark quality --dataset public \
  --output benchmark-results/latest/quality --format json,md,csv
```

Release gates:

- `hit_at_3 >= 0.95`, `adapter_success_rate = 1.0` (quick)
- `empty_correct_rate >= 0.67`, `provenance_completeness >= 0.95`,
  `openwebui_success_rate = 1.0`, `opencode_success_rate = 1.0`
  (quality)

Include the relevant JSON summary in the PR description if your change
moves any of these numbers.

## Security

See [SECURITY.md](SECURITY.md). Do not file vulnerabilities as public
issues.
