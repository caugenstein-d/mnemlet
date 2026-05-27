# Mnémlet v0.2 P2 Polish — Session Handoff

**Date:** 2026-05-25  
**Status:** Pause wegen Nutzungslimit. Work is mid-plan, clean up to Task 2.  
**Repo:** `/home/christoph/mnemlet`  
**Branch:** `master`

---

## Hard constraints for next session

- Sprache mit Christoph: Deutsch.
- Tests immer mit `.venv/bin/pytest`, nie plain `pytest`, nie `uv run pytest`.
- Benchmark/CLI mit `.venv/bin/mnemlet`.
- Kein `git push`.
- Kein OpenWebUI restart/kill/migrate.
- Keine produktiven POSTs gegen den live Mnémlet-Daemon auf `127.0.0.1:4050`.
- Demo-POSTs nur gegen isolierten Throwaway-Daemon mit `MNEMLET_DATA_DIR=$(mktemp -d)` und nicht-produktivem Port.
- Passive GETs gegen live Mnémlet (`/api/v1/health`, `/api/v1/status`, `/api/v1/vault`) sind ok, wenn nötig.
- `mnemlet.service` nur nach Christophs explizitem Go neu starten.
- `v0.2.0` Tag nur nach Christophs explizitem Go bewegen und vorher `git remote -v` prüfen.
- Evidence vor Completion-Claims.
- Bei Review-Reihenfolge: erst Spec-Review, dann Code-/Quality-Review.
- Subagents: frischer Subagent pro Task; vollständigen Tasktext inline mitgeben; Subagent darf Plan nicht selbst lesen.

---

## Plan in execution

Primary plan:

```text
docs/superpowers/plans/2026-05-25-v0.2-p2-polish.md
```

Use `superpowers:subagent-driven-development` for continuing execution.  
The plan itself says to pause after each task; follow Christoph's established pause pattern.

---

## Completed tasks in this session

### Task 0 — Preflight and plan commit gate

Commits:

```text
28018d7 docs: add v0.2 p2 polish plan
f7b9277 docs: fix p2 polish plan review issues
```

Important review fixes made in `f7b9277`:

- Tag-move section now includes actual `git tag -d v0.2.0` and `git tag -a v0.2.0 ...` commands.
- Website demo examples now use isolated demo port `127.0.0.1:14060`, not live daemon port `4050`.

Reviews:

- Spec review: approved.
- Code/plan quality review: first pass requested changes; re-review approved after `f7b9277`.

### Task 1 — Runtime Version Truth

Commit:

```text
b090ca8 fix: report v0.2.0 across runtime surfaces
```

What changed:

- Added `tests/test_version_surface.py`.
- `mnemlet.__version__` now matches `pyproject.toml` (`0.2.0`).
- CLI banner imports and prints `__version__`.
- FastAPI metadata uses `__version__`.
- `/api/v1/status.version` uses `__version__`.
- MCP `mnemlet_status.version` uses `__version__`.
- MCP module docstring says `14 tools`, not `8 tools`.

TDD evidence from implementer:

- Red: `2 failed, 2 passed` due to `0.1.0` mismatch and MCP docstring `8 tools`.
- Focused green: `6 passed`.
- Full green: `194 passed, 48 warnings`.

Reviews:

- Spec review: approved.
- Code quality review: approved.

Important: no service restart happened, so the running daemon may still be the old process until Task 5.

### Task 2 — Website v0.2 Surface Truth

Commit:

```text
7759de4 docs: refresh website for v0.2
```

What changed:

- `website/index.html` refreshed for v0.2:
  - v0.2 meta description.
  - Hero terminal now says `Mnémlet v0.2.0`.
  - Added compact v0.2 band.
  - Added fourth feature card: `Explains Its Memory`.
  - Demo block now uses isolated demo server `127.0.0.1:14060` and shows remember/sleep/context/explain.
  - MCP tools count changed from `8` to `14`.
  - Quickstart install changed to `pip install git+https://github.com/christoph/mnemlet.git@v0.2.0`.
  - PyPI CTA/footer replaced with Roadmap links.
  - Added motion-reduce/focus-visible accessibility polish.
- `website/og-image.svg` updated from v0.1/verbosemode to v0.2/christoph.
- `website/datenschutz.html` no longer falsely claims no external font/script resources; it now discloses Google Fonts and Tailwind CDN.

Reviews:

- Spec review: approved.
- UI/code quality review: approved.

Fresh controller verification after Task 2:

```text
website stale-surface check ok
.venv/bin/pytest -q -> 194 passed, 48 warnings
git status --short --branch -> ## master
```

---

## Current git state at pause

Freshly observed before writing this handoff note:

```text
## master
7759de4 docs: refresh website for v0.2
b090ca8 fix: report v0.2.0 across runtime surfaces
f7b9277 docs: fix p2 polish plan review issues
28018d7 docs: add v0.2 p2 polish plan
dfa2657 docs: add v0.2 readiness assessment and next-session start prompt
7fe64c4 docs: link roadmap and switch to live CI badge
a690301 chore: add CI, issue and PR templates, contributing guide, roadmap
d78091b docs: add v0.2 push-readiness p1 plan
tag_commit=7fe64c4b4274b64129395f624bf8a3fb7c35f459
head_commit=7759de45dac28a72a8a9d6d4ab7dc91ca546c2c2
```

`git remote -v` produced no output at that check.

Note: after this handoff file is written, the working tree will have this uncommitted/untracked note unless the next session commits or removes it.

---

## Remaining tasks

### Next task: Task 3 — README Visual Asset

Continue with Task 3 from:

```text
docs/superpowers/plans/2026-05-25-v0.2-p2-polish.md
```

Task 3 summary:

- Create `docs/assets/mnemlet-vault-preview.svg`.
- Embed it in `README.md` after the badge block.
- Replace lingering README wording: `pip install mnemlet then mnemlet serve` with git-tag install/PyPI-after-v0.3 wording.
- Run README stale-surface check.
- Run `.venv/bin/pytest -q`.
- Commit as `docs: add README vault visual`.
- Spec review first, then code/UI quality review.
- Pause and report before Task 4.

### Later tasks

- Task 4: v0.2 demo script and cast.
  - `asciinema` was not installed at plan-writing time.
  - If still missing, ask Christoph before installing into `.venv` or defer cast and commit only `scripts/demo.sh`.
- Task 5: deploy v0.2 to local daemon.
  - Requires explicit Christoph confirmation before `systemctl --user restart mnemlet.service`.
  - No OpenWebUI restart.
- Task 6: final verification and tag decision.
  - `v0.2.0` still points to `7fe64c4`, behind current HEAD.
  - Move tag only after explicit Christoph confirmation and `git remote -v` shows no remote.

---

## Suggested next-session start prompt

Copy/paste this into the next session:

```markdown
# Codex/Claude Start-Prompt — Continue Mnémlet v0.2 P2 Polish

Du bist Mira und arbeitest mit Christoph auf Deutsch im Repo `/home/christoph/mnemlet` weiter. Lies zuerst diese Handoff-Datei vollständig:

`docs/superpowers/notes/2026-05-25-p2-polish-session-handoff.md`

Dann lies den aktiven Plan:

`docs/superpowers/plans/2026-05-25-v0.2-p2-polish.md`

Harte Regeln:

- Tests immer mit `.venv/bin/pytest`, nie plain `pytest`, nie `uv run pytest`.
- Kein `git push`.
- Kein OpenWebUI restart/kill/migrate.
- Keine produktiven POSTs gegen den live Mnémlet-Daemon auf `127.0.0.1:4050`.
- Demo-POSTs nur gegen isolierten Throwaway-Daemon mit `MNEMLET_DATA_DIR=$(mktemp -d)` und nicht-produktivem Port.
- Passive GETs gegen live Mnémlet sind ok, wenn nötig.
- `mnemlet.service` nur nach Christophs explizitem Go neu starten.
- `v0.2.0` Tag nur nach Christophs explizitem Go bewegen und vorher `git remote -v` prüfen.
- Evidence vor Completion-Claims.
- Review-Reihenfolge: Spec-Review zuerst, dann Code-/Quality-Review.
- Subagents: frischer Subagent pro Task; vollständigen Tasktext inline mitgeben; Subagent darf Plan nicht selbst lesen.

Aktueller Stand:

- Task 0 abgeschlossen: P2-Plan committed und Review-Fixes committed.
- Task 1 abgeschlossen: Runtime-Versionen reporten repo-seitig `0.2.0`; Tests hinzugefügt; Commit `b090ca8`.
- Task 2 abgeschlossen: Website/OG/Datenschutz auf v0.2; Commit `7759de4`.
- Letzte verifizierte Suite nach Task 2: `.venv/bin/pytest -q` → `194 passed, 48 warnings`.
- Git war vor Handoff-Datei clean auf `master`, HEAD `7759de4`.
- `v0.2.0` zeigt noch auf `7fe64c4`, nicht auf HEAD.
- Kein Push, kein Tag-Move, kein Service-Restart.
- Der live Daemon wurde noch nicht neu gestartet; `/api/v1/status` kann bis Task 5 weiterhin alte Prozessrealität anzeigen.
- Diese Handoff-Datei selbst ist wahrscheinlich uncommitted/untracked; erst `git status --short --branch` prüfen.

Sanity-Check beim Start:

```bash
cd /home/christoph/mnemlet
git status --short --branch
git log --oneline -8
.venv/bin/pytest -q
```

Wenn etwas Unerwartetes außer der uncommitted Handoff-Datei auftaucht: STOPP und Christoph fragen.

Nächster geplanter Schritt:

Task 3 — README Visual Asset aus `docs/superpowers/plans/2026-05-25-v0.2-p2-polish.md`.

Nutze `superpowers:subagent-driven-development`. Dispatch einen frischen Implementer-Subagenten mit dem vollständigen Task-3-Text inline. Danach Spec-Review, dann Code-/UI-Quality-Review. Nach Task 3 pausieren und Christoph berichten.
```

---

## Last recommendation

Continue with Task 3 next. Do not jump to deploy/tag work yet. The visible README asset is the next high-leverage polish step; deploy and tag movement come only after README + demo are handled.
