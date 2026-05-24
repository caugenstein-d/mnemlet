# Codex Start-Prompt — Nächste Session (Mnémlet v0.2 Post-Push-Readiness)

> Geschrieben am 2026-05-24, Abend. Für die nächste Session.
> Wenn diese Session wieder Codex übernimmt, lies diesen Prompt zuerst
> komplett durch, dann das Bewertungs-Dokument
> `docs/superpowers/notes/2026-05-24-v0.2-readiness-assessment.md`,
> dann frag Christoph, welche Option als nächstes dran ist.

---

## Wer du bist und was du machst

Du übernimmst die Mnémlet-Weiterarbeit nach einer abgeschlossenen
Push-Readiness-Phase (Release-Bump + P0 Surface-Wahrheit + P1 Community-
Hygiene). Mira (Claude) hat heute alle drei Bündel zu Ende gebracht und
das Repo in einen push-fähigen Stand gehoben.

**Es ist nichts auf GitHub gepusht.** Es gibt nicht mal eine `origin`-
Remote. Christoph entscheidet, wann und wie gepusht wird.

---

## Harte Constraints (nicht herleiten — wörtlich befolgen)

- Sprache mit Christoph: **Deutsch**, korrekte Umlaute (ä/ö/ü/ß, é).
- Tests IMMER mit `.venv/bin/pytest`, NICHT plain `pytest`,
  NICHT `uv run pytest`. `uv` ist nicht installiert.
- Benchmark-CLI mit `.venv/bin/mnemlet`.
- **KEIN git push** (kein remote ist konfiguriert; auch wenn eines
  hinzukommt, kein push ohne explizite Aufforderung).
- **KEIN OpenWebUI restart/kill/migrate**.
- **KEINE produktiven Chat-POSTs** gegen OpenWebUI oder Mnémlet.
- Passive Read-Only-Calls gegen den lokalen Mnémlet-Daemon
  (`/api/v1/health`, `/api/v1/status`, `/api/v1/vault`) sind OK,
  wenn die Aufgabe sie erfordert. KEINE ingest/forget/replace/confirm-
  POSTs gegen den laufenden Daemon.
- Evidence vor Completion-Claims.
- Wenn du Subagents nutzt: frischer Subagent pro Phase,
  vollständigen Tasktext inline mitgeben; Subagent darf Plan NICHT
  selbst lesen.
- Reihenfolge bei Review: Spec-Review zuerst, dann Code-Quality-Review.

---

## Arbeitsumgebung

- **Hauptrepo:** `/home/christoph/mnemlet`
- **Branch:** `master`
- **Worktrees:** keine offenen (`fix/v0.2-quality-hardening` ist
  abgeschlossen, gemergt, Worktree entfernt, Branch gelöscht).
- **Remotes:** keine (verifiziert per `git remote -v` — leer).
- **Python:** `.venv/bin/python` (Python 3.12).

Aufpassen: das Bash-Tool hat in der letzten Session mehrfach den cwd
verloren. **Immer `cd /home/christoph/mnemlet && …`** vor Git/Test-
Befehlen, sonst greifen sie ins Heimverzeichnis.

---

## Projektstand (heute, 2026-05-24 Abend)

### Git
- HEAD: `7fe64c4 docs: link roadmap and switch to live CI badge`
- Tag `v0.2.0` (annotated) zeigt auf HEAD
- Letzte 9 Commits (neueste oben):
  ```
  7fe64c4 docs: link roadmap and switch to live CI badge
  a690301 chore: add CI, issue and PR templates, contributing guide, roadmap
  d78091b docs: add v0.2 push-readiness p1 plan
  123748c docs: align v0.2 surface with code
  cb0102f docs: add v0.2 push-readiness plan
  baead96 release: v0.2.0
  7fe64c4… (siehe oben)
  ```
- Working tree: clean.

### Tests und Benchmarks (verifiziert heute)
- `.venv/bin/pytest -q` → **190 passed**, 47 warnings, ~77s
- quick: `hit_at_3=1.0`, `adapter_success_rate=1.0`
- quality: `empty_correct_rate=1.0`, `provenance_completeness=1.0`,
  `openwebui_success_rate=1.0`, `opencode_success_rate=1.0`

### Live-Daemon (verifiziert heute via passivem Health-Check)
- `localhost:4050` antwortet.
- 58 active memories, 1 cold storage memory, 7883 total interactions,
  54 chroma documents.
- **`version: 0.1.0`** ← der laufende Daemon ist NICHT v0.2.0.
  Repo und produktive Realität klaffen auseinander.

### Push-Readiness-Surface (heute erledigt)
- `pyproject.toml` 0.2.0, `README.md` v0.2-wahr (14 Tools, 17 Routes,
  git+install), `AGENTS.md` v0.2, `CHANGELOG.md`, `ROADMAP.md`,
  `CONTRIBUTING.md` (82 Zeilen), `.github/workflows/test.yml`,
  Issue-/PR-Templates, README-CI-Badge + Roadmap-Sektion.

---

## Pflichtlektüre vor der ersten Antwort

1. **Bewertungs-Dokument:**
   `docs/superpowers/notes/2026-05-24-v0.2-readiness-assessment.md`
   — ehrliche Lage (Stärken, Schwächen, Markt mit OpenClaw-Kontext,
   Wow-Chancen, was fehlt).
2. **Beide Push-Readiness-Pläne** (Status-Spur, nicht zur Ausführung):
   `docs/superpowers/plans/2026-05-24-v0.2-push-readiness.md` (P0,
   abgeschlossen)
   `docs/superpowers/plans/2026-05-24-v0.2-push-readiness-p1.md` (P1,
   abgeschlossen)
3. **Trust/Security/Privacy Spec** (für eine eventuelle v0.3-Diskussion
   oder Plan-Erstellung):
   `docs/superpowers/specs/2026-05-22-trust-security-privacy-layer-design.md`

Lies erst, dann frag. Nicht aus der Erinnerung antworten — diese Dokumente
sind die Wahrheit.

---

## Worüber Christoph wahrscheinlich entscheiden lassen will

Reihenfolge nach Reife (oben = klein und hoch-Hebel, unten = größer):

### Option 1 — P2 Polish-Bündel (für "stillen Push" ready)
Geschätzt 1 Session, mehrere Tasks mit Pause dazwischen.
- `scripts/demo.cast` neu aufnehmen (asciinema) gegen v0.2:
  ingest → sleep cycle → morning briefing → recall mit provenance +
  explain. **Braucht Christoph-Interaktion** (Terminal-Session).
- `website/index.html` auf v0.2-Stand bringen (zeigt aktuell v0.1
  Feature-Set vom 19. Mai).
- Ein Screenshot oder kurzes GIF ins README — Empfehlung:
  Markdown-Vault in Obsidian (kein anderer Memory-Engine-Mitbewerber
  hat das visuelle Asset).
- v0.2-Deploy auf den Pi-Daemon, damit `/api/v1/status` 0.2.0 meldet.
  **Braucht Christoph-Bestätigung**, weil das den laufenden Service
  neustartet.

### Option 2 — v0.3 Plan (Trust/Security/Privacy)
Spec existiert, Plan fehlt. Vier P0-Features ("Muss haben"):
Single API Key Auth, Secret Regex Guard, Audit Log, Startup-Security-
Check. Drei P1-Features als Stretch. Vorgehen analog v0.2 Quality
Hardening (Worktree, subagent-driven, Spec-Review → Code-Quality-Review).

### Option 3 — PyPI Publish Plan
Brauchst Token, Build via `python -m build`, Test-Install, Publish,
Post-Publish-Smoke-Test. Macht `pip install mnemlet` zur Wahrheit
(aktuell nur `git+…@v0.2.0`).

### Option 4 — Push vorbereiten (still oder laut)
Setzt `git remote add origin …` voraus. Stiller Push: jetzt möglich.
Lauter Launch (r/selfhosted, HN): erst nach v0.3 + Demo + Website +
optional Video. Siehe Bewertung für Begründung.

---

## Empfehlung an Christoph (nicht selbst entscheiden — vorschlagen)

In der Bewertung steht eine Sequenz-Empfehlung (Polish → v0.3 → PyPI →
lauter Launch). Wenn Christoph nicht selbst priorisiert, schlag **Option 1
(P2 Polish)** vor als nächsten kleinen, hoch-Hebel-Schritt — und mach
für genau dieses Bündel den gleichen Plan-niederschreiben-vor-Pause-
Workflow wie heute für P0 und P1.

---

## Workflow-Pattern (heute etabliert, weiter so)

1. Plan komplett niederschreiben **vor** der Implementierung
   (Datei unter `docs/superpowers/plans/`).
2. Pause vor jedem Task.
3. Pro Task: präzise Steps, klare Akzeptanz, kein Geschwurbel.
4. Out of Scope explizit benennen (vermeidet Scope-Creep).
5. Tag `v0.2.0` lokal nach jedem Bündel auf neuen HEAD verschieben
   (sicher solange kein push erfolgte; Pre-Flight per `git remote -v`
   ist Pflicht).
6. Drei Commits pro Bündel (Plan / Implementation / README/Surface-
   Polish) — Repo-Muster bestehender Plans.
7. Subagent-Tasks: vollständigen Text inline, Subagent darf den Plan
   nicht lesen.

---

## Bekannte Minor Notes (nicht-blockierend, im Hinterkopf)

Aus v0.2-Hardening, weiter offen, NICHT eigenmächtig fixen:
- Kein Direkt-Test für `assert_score_increased` mit fehlender Memory.
- `tests/fixtures/openwebui/mnemlet_valve.py` importiert ungenutztes
  `urllib.error`.
- Fixture-Drift-Risiko: volle Filter-Kopie liegt im Repo statt
  generiert.
- `QualityRunner.run()` ruft `setup()` vor innerem try/finally;
  äußeres Cleanup steht in `run_quality_benchmark()`.

---

## Sanity-Check beim Start

Bevor du dich an Optionen ranmachst:

```bash
cd /home/christoph/mnemlet
git status --short --branch        # erwarte: clean, master
git log --oneline -5               # erwarte: HEAD 7fe64c4
git tag                            # erwarte: v0.2.0
git rev-parse v0.2.0^{commit}      # erwarte: gleich wie git rev-parse HEAD
git remote -v                      # erwarte: leer
.venv/bin/pytest -q                # erwarte: 190 passed
```

Wenn irgendwas abweicht: STOPP, Christoph fragen, nichts überschreiben.

---

## Letzte Bitte an dich

Christoph arbeitet bewusst mit Pausen zwischen Tasks, um nicht ans
Nutzungslimit zu kommen. Halte das Pattern ein. Lieber zu oft pausieren
und Bescheid sagen "Task X fertig, Evidence Y, weiter?" als einen
langen Marathon-Lauf, der mitten im nächsten Bündel abreißt.

Und denk dran: Mnémlet ist sein Projekt, du bist Hilfskraft. Vorschläge
ja, eigenmächtige Richtungswechsel nein.
