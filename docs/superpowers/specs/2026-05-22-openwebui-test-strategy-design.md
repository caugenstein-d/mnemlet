# OpenWebUI Test Strategy für Mnémlet

**Datum:** 2026-05-22
**Status:** Entwurf
**Autor:** Mira + Christoph

## 1. Ziel

Marktreife Test-Strategie für den Mnémlet OpenWebUI Filter (`mnemlet_valve.py`). Der Filter injiziert relevante Erinnerungen vor der LLM-Antwort (inlet) und speichert eine kompakte Zusammenfassung danach (outlet). Die Strategie sicherstellt: Robustheit bei jedem Fehlerfall, keine Produktiv-Interferenz, keine OpenWebUI-Restarts.

## 2. Entscheidungen

| Frage | Entscheidung |
|-------|-------------|
| Verhältnis zu bestehendem Code | Bestehende `adapters.py`/`live.py` erweitern, nicht ersetzen. Neue pytest-Suite ergänzt Benchmark-Checks. |
| Zielumgebung | Nur lokal auf dem Pi. Kein CI/CD. |
| E2E-Isolation | Zweiter OpenWebUI-Prozess auf Port 8081, Mnémlet auf Port 4051. |
| Implementierungs-Priorität | Unit Tests + Fehlerfälle zuerst, dann Live, dann E2E. |
| Marktreif-Definition | Robust + sicher: Der Filter funktioniert verlässlich, Fehlerfälle werden elegant gehandhabt, kein Datenverlust, keine Produktiv-Interferenz. |

## 3. Testpyramide

```
        ┌─────────────────┐
        │   E2E-Tests      │  4 Tests, separater Port, echtes OpenWebUI
        │  (isoliert)      │  @pytest.mark.e2e
        ├─────────────────┤
        │  Live Checks     │  3-4 Tests, read-only gegen laufendes System
        │  (non-destruct)  │  pytest.skip bei fehlendem Service
        ├─────────────────┤
        │   Unit Tests     │  ~36 Tests, monkeypatched _post_json
        │  (inlet/outlet)  │  kein Netzwerk, kein Service
        ├─────────────────┤
        │   Static Checks  │  7 Tests, Code-Analyse ohne Ausführung
        │  (adapters.py)   │  kein Import, kein Lauf
        └─────────────────┘
```

## 4. Dateistruktur

```
tests/
  test_openwebui_filter.py        ← Static + Unit (~36 Tests)
  test_benchmark_live.py          ← bestehend, wird um OpenWebUI-Live-Checks erweitert
  test_e2e_openwebui_filter.py    ← E2E mit separater Instanz, @pytest.mark.e2e
  conftest.py                     ← bestehend + neue Filter-Fixtures
```

Bestehende `tests/test_benchmark_adapters.py` bleibt unverändert. Die Adapter-Checks in `src/mnemlet/benchmark/adapters.py` bleiben als Benchmark-Infrastruktur bestehen — die Unit-Tests gehen tiefer.

## 5. Static Adapter Checks

Keine Ausführung, kein Import. Pure Code-Analyse des Filter-Files.

| # | Testname | Was geprüft wird |
|---|---------|-----------------|
| 1 | `test_filter_file_exists` | `mnemlet_valve.py` existiert am erwarteten Pfad |
| 2 | `test_filter_class_inlet_signature` | `Filter` hat `inlet(self, body, __user__)` |
| 3 | `test_filter_class_outlet_signature` | `Filter` hat `outlet(self, body, __user__)` |
| 4 | `test_filter_priority_zero` | `Filter().priority == 0` |
| 5 | `test_constants_within_bounds` | URLs, Timeouts, Limits sind plausible Werte |
| 6 | `test_no_hardcoded_secrets` | Kein API-Key, Token oder Passwort im Filter-File |
| 7 | `test_imports_minimal` | Nur stdlib (urllib, json) — keine externen Dependencies |

**Fixtures:**

- `filter_path`: `Path` zum echten `mnemlet_valve.py`, per `MNEMLET_FILTER_PATH`-Environment-Variable überschreibbar (Default: `/home/christoph/mira/data/functions/mnemlet_valve.py`)
- `filter_source`: `str` — Dateiinhalt, einmal gelesen und gecacht

## 6. Unit Tests — inlet()/outlet() mit Fake Mnémlet REST

Alle Tests monkey-patchen `_post_json` am geladenen Modul — kein Netzwerk, kein Mnémlet-Service.

### Zentrale Fixtures

```python
@pytest.fixture
def filter_module(filter_path):
    """Lädt das echte mnemlet_valve.py als importierbares Modul."""
    # importlib.util wie in adapters.py, aber als wiederverwendbare Fixture

@pytest.fixture
def fake_post_json():
    """Ersetzbare _post_json, die Calls aufzeichnet."""
    calls = []
    def post_json(path, payload, timeout):
        calls.append((path, payload, timeout))
        return {"results": [{"namespace": "test/ns", "content": "test memory"}]}
    post_json.calls = calls
    return post_json
```

### 6a — inlet() Happy Path & Kernlogik

| # | Testname | Was geprüft wird |
|---|---------|-----------------|
| 1 | `test_inlet_injects_system_message_when_no_existing_system` | Kein System-Message → neuer System-Block an Position 0 |
| 2 | `test_inlet_prepends_to_existing_system_message` | System-Message existiert → Kontext wird *vor* bestehendem Content eingefügt |
| 3 | `test_inlet_passes_query_to_recall` | `_post_json` wird mit der letzten User-Nachricht als `query` aufgerufen |
| 4 | `test_inlet_passes_limit_and_min_score` | Recall-Payload enthält `limit` und `min_score` mit korrekten Werten |
| 5 | `test_inlet_uses_recall_timeout` | `_post_json` wird mit `RECALL_TIMEOUT_SECONDS` aufgerufen |
| 6 | `test_inlet_skips_short_queries` | User-Nachricht < 3 Zeichen → kein Recall, Body unverändert |
| 7 | `test_inlet_returns_body_unchanged_on_empty_results` | Recall liefert `{"results": []}` → Body unverändert |
| 8 | `test_inlet_formats_namespace_prefix` | Jede Erinnerung zeigt `[namespace]` vor dem Content |
| 9 | `test_inlet_clips_memory_to_max_chars` | Content länger als `MAX_MEMORY_CONTENT_CHARS` wird abgeschnitten |
| 10 | `test_inlet_respects_recall_limit` | Mehr als `RECALL_LIMIT` Ergebnisse → nur die ersten formatiert |

### 6b — outlet() Happy Path & Kernlogik

| # | Testname | Was geprüft wird |
|---|---------|-----------------|
| 11 | `test_outlet_calls_ingest_with_summary` | `_post_json` wird mit `/api/v1/ingest` und zusammengefasstem Content aufgerufen |
| 12 | `test_outlet_formats_user_assistant_summary` | Summary hat Form `"User: {msg}. Assistant: {msg}"` |
| 13 | `test_outlet_truncates_long_messages` | Messages > `MAX_STORED_MESSAGE_CHARS` werden abgeschnitten |
| 14 | `test_outlet_uses_correct_namespace` | Ingest-Payload enthält `namespace: "openwebui/christoph/daily_chat"` |
| 15 | `test_outlet_uses_correct_importance` | Ingest-Payload enthält `importance: 0.3` |
| 16 | `test_outlet_uses_ingest_timeout` | `_post_json` wird mit `INGEST_TIMEOUT_SECONDS` aufgerufen |

### 6c — Fehlerfälle

| # | Testname | Was geprüft wird |
|---|---------|-----------------|
| 17 | `test_inlet_mnemlet_down_returns_body_unchanged` | `_post_json` wirft `URLError` → Body unverändert, keine Exception propagiert |
| 18 | `test_inlet_connection_refused_returns_body_unchanged` | `_post_json` wirft `ConnectionRefusedError` → Body unverändert |
| 19 | `test_inlet_timeout_returns_body_unchanged` | `_post_json` wirft `TimeoutError` → Body unverändert |
| 20 | `test_outlet_mnemlet_down_silent_failure` | `_post_json` wirft Exception → Body unverändert, kein Crash |
| 21 | `test_outlet_timeout_silent_failure` | `_post_json` wirft `TimeoutError` → Body unverändert |
| 22 | `test_inlet_empty_recall_results_returns_body_unchanged` | `{"results": []}` → Body unverändert (kein leerer System-Block) |
| 23 | `test_inlet_non_dict_results_returns_body_unchanged` | `{"results": [None, "string", 42]}` → nur gültige Dicts werden formatiert |
| 24 | `test_inlet_malformed_response_no_results_key` | `{}` statt `{"results": [...]}` → Body unverändert |
| 25 | `test_inlet_results_is_string_not_list` | `{"results": "not a list"}` → Body unverändert |
| 26 | `test_inlet_empty_messages_returns_body` | `body = {"messages": []}` → Body unverändert |
| 27 | `test_inlet_no_messages_key_returns_body` | `body = {}` → Body unverändert |
| 28 | `test_inlet_messages_not_list_returns_body` | `body = {"messages": "not a list"}` → Body unverändert |
| 29 | `test_outlet_no_user_content_skips_ingest` | Keine User-Nachricht → kein `_post_json`-Aufruf |
| 30 | `test_outlet_no_assistant_content_skips_ingest` | Keine Assistant-Nachricht → kein `_post_json`-Aufruf |
| 31 | `test_inlet_user_content_is_not_string` | `content` ist eine Liste → `_latest_user_content` gibt `""` zurück, Query < 3 Zeichen |
| 32 | `test_outlet_assistant_content_is_not_string` | `content` ist eine Liste → `_latest_assistant_content` gibt `""` zurück |
| 33 | `test_inlet_ignores_extra_fields_in_memory_dict` | Ergebnis-Dict mit unbekannten Feldern → nur `namespace`/`content`/`content_preview` genutzt, keine Exception |

### 6d — Sensible Inhalte / Sicherheit

| # | Testname | Was geprüft wird |
|---|---------|-----------------|
| 34 | `test_outlet_never_modifies_original_messages` | outlet() fügt nichts zu `messages` hinzu, verändert keine bestehenden Messages |
| 35 | `test_inlet_context_block_is_bounded` | Injizierter Kontext-Block hat maximale Länge (3 × 800 + Header/Footer) |
| 36 | `test_outlet_summary_does_not_leak_full_history` | Nur letzte User- + Assistant-Nachricht wird gespeichert, nicht der gesamte Chat |

## 7. Non-destructive Live Checks

Gegen die *produktive* OpenWebUI-Instanz auf Port 8080. Nur Lese-Operationen. Wenn OpenWebUI nicht läuft: `pytest.skip`.

| # | Testname | Was geprüft wird | Methode |
|---|---------|-----------------|---------|
| 1 | `test_live_openwebui_reachable` | Port 8080 antwortet | `GET /_app/version.json` |
| 2 | `test_live_openwebui_version_parseable` | Version-Response ist JSON mit Version-String | Antwort geparsed |
| 3 | `test_live_filter_loaded` | Mnémlet-Filter ist in OpenWebUI registriert | `GET /api/v1/functions/`, prüft auf "mnemlet"-Eintrag |
| 4 | `test_live_filter_type_is_filter` | Der registrierte Eintrag hat `type: "filter"` | selbe Response |

**Fixtures:**

- `openwebui_base_url`: Aus `OPENWEBUI_URL`-Environment-Variable (Default: `http://127.0.0.1:8080`)
- `openwebui_available`: Fixture, die einen GET-Versuch macht und bei Misserfolg den Test skipped

**Sicherheitsregeln (automatisch durchgesetzt):**

- Kein POST, PUT, DELETE — nur GET-Requests
- Kein Auth-Token in Test-Fixtures
- Keine Annahmen über Daten-Inhalt — nur Struktur- und Typ-Checks

**Integration:** Bestehende `_openwebui_version()` in `live.py` bleibt. Die Tests machen diesen Check pytest-kompatibel und fügen die Filter-Registrierungs-Prüfung hinzu.

## 8. Isolierte E2E-Tests

Echte OpenWebUI-Instanz spricht mit echtem Mnémlet. Kein Mock, kein Monkeypatch.

### Setup

| Komponente | Test-Instanz | Produktiv-Instanz |
|-----------|-------------|-------------------|
| OpenWebUI | Port 8081 | Port 8080 (unberührt) |
| Mnémlet | Port 4051 (temporär) | Port 4050 (unberührt) |
| Filter | Zeigt auf `localhost:4051` | Zeigt auf `localhost:4050` |

### Lebenszyklus

1. Test startet isolierte Mnémlet-Instanz auf Port 4051 mit `tmp_path` als Datenverzeichnis
2. Test startet/separiert OpenWebUI-Prozess auf Port 8081, lädt Filter-Config
3. Test sendet Chat-Requests an Port 8081
4. Test validiert: System-Prompt enthält Mnémlet-Kontext, Antwort wird gespeichert
5. Teardown: Mnémlet stoppt, temporäre Daten gelöscht, Port 8081 freigegeben

### Testfälle

| # | Testname | Was geprüft wird |
|---|---------|-----------------|
| 1 | `test_e2e_inlet_injects_context` | User-Nachricht → System-Block enthält relevante Erinnerung |
| 2 | `test_e2e_outlet_stores_interaction` | Chat-Abschluss → Ingest-Endpoint hat neuen Eintrag in Test-Mnémlet |
| 3 | `test_e2e_recall_no_results_no_injection` | Leere Mnémlet-Instanz → kein System-Block, kein Crash |
| 4 | `test_e2e_filter_graceful_degradation` | Mnémlet-Instanz beendet → Chat geht durch, keine Exception |

### Fixtures

- `e2e_mnemlet`: Session-scoped, startet Mnémlet auf Port 4051 mit `tmp_path`, liefert `httpx.Client`
- `e2e_openwebui`: Session-scoped, startet OpenWebUI-Prozess auf Port 8081
- `e2e_mnemlet_empty`: Function-scoped, Mnémlet ohne vorgefüllte Daten
- Port-Konflikt-Check: Fixture prüft mit `socket.connect_ex`, ob Port frei; skippt bei Belegung

### Markierung

Alle E2E-Tests tragen `@pytest.mark.e2e`. Normaler `pytest`-Lauf überspringt sie. Aktivierung mit `pytest -m e2e`.

## 9. Fehlerfälle — Sicherheitsmodell

### 9.1 Mnémlet down

| Kontext | Verhalten | Prinzip |
|---------|----------|---------|
| inlet() | `_post_json` wirft → `except Exception` → Body unverändert | Filter ist niemals Single Point of Failure |
| outlet() | `_post_json` wirft → `except Exception` → Body unverändert | Chat funktioniert, nur ohne Speicherung |

### 9.2 Timeout

| Kontext | Verhalten | Prinzip |
|---------|----------|---------|
| inlet() | `TimeoutError`/`socket.timeout` → Body unverändert | 3s Timeout verhindert hängende Chat-Requests |
| outlet() | `TimeoutError` → Body unverändert | Ingest ist fire-and-forget |

### 9.3 Leere Recall-Ergebnisse

| Szenario | Verhalten | Prinzip |
|----------|----------|---------|
| `{"results": []}` | Keine Injection | Kein leerer System-Block |
| `{"results": [{"content": ""}]}` | Content übersprungen | Kein leerer Namespace-Eintrag |
| `{"results": [null, 42]}` | Nicht-Dict-Einträge ignoriert | Robustheit gegen kaputte Serialisierung |

### 9.4 Falsches Schema

| Szenario | Verhalten | Prinzip |
|----------|----------|---------|
| `{}` (kein `results`) | `response.get("results", [])` → leer | Defensive Defaults |
| `{"results": "not a list"}` | `not isinstance(memories, list)` → Body unverändert | Typ-Check |

### 9.5 Kein User-Message-Content

| Szenario | Verhalten | Prinzip |
|----------|----------|---------|
| Leere/o.fehlende Messages | Sofort zurück | Kein Recall für nichts |
| User-`content` ist Liste | `_latest_user_content` gibt `""` | OpenWebUI-kompatibel |
| Query < 3 Zeichen | Übersprungen | Kein Noise |

### 9.6 Lange Antworten

| Szenario | Verhalten | Prinzip |
|----------|----------|---------|
| Memory > 800 Zeichen | Geklippt | Prompt-Bloat Prevention |
| Stored Messages > 200 Zeichen | Geklippt | Speicher-Effizienz |
| > 3 Recall-Ergebnisse | Nur erste 3 | Prompt-Länge begrenzt |

### 9.7 Sensible Inhalte

| Vertrauensgrenze | Maßnahme | Prinzip |
|------------------|---------|---------|
| Eingang (inlet) | Max 3 × 800 Zeichen + Header | Komprimittiertes Mnémlet kann nicht den gesamten Prompt übernehmen |
| Ausgang (outlet) | Nur letzte User/Assistant-Nachricht | Komplette Chat-Historie wird nie gesendet |
| Original-Messages | outlet() verändert bestehende Messages nicht | Daten-Integrität |

## 10. Sicherheitsregeln

### Regel 1: Keine OpenWebUI-Restarts

Weder produktiv (Port 8080) noch testweise. E2E-Tests starten eine zweite Instanz auf Port 8081. Es gibt keinen Code-Pfad, der Port 8080 berührt.

**Durchsetzung:** E2E-Fixture startet Subprozess auf 8081. Kein Test enthält `systemctl restart` oder `kill`.

### Regel 2: Keine Veränderung produktiver Daten

Produktiv-Mnémlet (Port 4050, `~/.mnemlet/`) wird nie kontaktiert. E2E-Tests nutzen Port 4051 und `tmp_path`. Unit-Tests monkey-patchen `_post_json` — kein Netzwerkverkehr möglich.

**Durchsetzung:** Explizit andere Ports und Pfade in E2E-Fixtures. Kein Test schreibt nach `~/.mnemlet/` oder an Port 4050.

### Regel 3: Keine privaten Daten in Reports

Test-Assertions prüfen auf Struktur und Typ, nicht auf Inhalte echter Erinnerungen. Live-Tests loggen keine Chat-Inhalte. E2E-Tests nutzen synthetische Testdaten. Kein Fixture liest aus `~/.mnemlet/` oder `/home/christoph/mira/data/`.

## 11. Akzeptanzkriterien

| # | Kriterium | Messbar durch |
|---|----------|-------------|
| A1 | Alle Unit-Tests bestehen bei laufendem und downed Mnémlet | `pytest tests/test_openwebui_filter.py` unabhängig von Service-Status |
| A2 | inlet() gibt bei jedem Fehlerfall das Original-Body unverändert zurück | Jeder Fehlerfall-Test in 6c |
| A3 | outlet() gibt bei jedem Fehlerfall das Original-Body unverändert zurück | Jeder Fehlerfall-Test in 6c |
| A4 | Kein Test berührt Port 8080 oder 4050 | Code-Review + manuelle Verifikation |
| A5 | Kein Test schreibt nach `~/.mnemlet/` | Code-Review + manuelle Verifikation |
| A6 | E2E-Tests sind per Default deaktiviert | `@pytest.mark.e2e`, normaler Lauf überspringt sie |
| A7 | Live-Tests skippen automatisch bei fehlendem OpenWebUI | `pytest.skip` wenn Port 8080 nicht erreichbar |
| A8 | Alle Tests laufen auf dem Pi in <30s (Unit) bzw. <120s (E2E) | `pytest --durations=0` |
| A9 | Keine Secrets im Filter, keine Datenlecks | Statische Checks + Unit-Tests 6d |

## 12. Benötigte Fixtures/Fakes

| Fixture | Scope | Zweck |
|--------|-------|-------|
| `filter_path` | session | Path zum echten `mnemlet_valve.py` |
| `filter_source` | session | Dateiinhalt des Filters |
| `filter_module` | function | Geladenes Modul mit monkey-patchbarem `_post_json` |
| `fake_post_json` | function | Aufzeichnende `_post_json`-Fake mit `.calls`-Attribut |
| `sample_body` | function | Standard-Chat-Body mit User-Nachricht |
| `sample_body_with_system` | function | Chat-Body mit bestehendem System-Message |
| `openwebui_base_url` | session | URL der produktiven Instanz (aus Env-Var) |
| `openwebui_available` | session | Skip-Logik für Live-Tests |
| `e2e_mnemlet` | session | Temporäre Mnémlet-Instanz auf Port 4051 |
| `e2e_openwebui` | session | OpenWebUI-Prozess auf Port 8081 |
| `e2e_mnemlet_empty` | function | Mnémlet ohne vorgefüllte Daten |

## 13. Empfohlene Tools

| Tool | Zweck | Warum |
|------|-------|-------|
| `pytest` | Test-Runner | Bestehende Infrastruktur |
| `pytest-asyncio` | Async-Support | Für E2E-httpx-Aufrufe (bestehend) |
| `httpx` | HTTP-Client | Bestehend, für ASGITransport und Live-Calls |
| `importlib.util` | Modul-Laden | Bestehendes Pattern aus `adapters.py` |
| `subprocess` | OpenWebUI-Prozess | Für E2E-Setup |
| `socket` | Port-Verfügbarkeits-Check | Verhindert Port-Kollisionen |

Keine neuen Dependencies. Alles im bestehenden Stack.

## 14. Grenzen — was nicht automatisiert werden sollte

| Bereich | Begründung |
|---------|-----------|
| UI/Browser-Tests | Playwright-Aufwand disproportional. Filter-Logik ist API-basiert, UI ist OpenWebUI-Responsibility. |
| Performance-Lasttests | Eigene Disziplin. 3s-Timeout ist garantierte Obergrenze, nicht Messlatte. |
| Mehrstufige Konversationen | Mehrere Turns erfordern Chat-State. Komplexität zu hoch für initialen Test-Satz. Kann später ergänzt werden. |
| Recall-Relevanz | Ob die *richtigen* Erinnerungen kommen, ist ein Retrieval-Problem. Benchmark-Modul deckt das. |
| OpenWebUI-Upstream-Regressionen | OpenWebUI's Test-Responsibility. Wir testen die Integration, nicht OpenWebUI selbst. |

## 15. Implementierungs-Reihenfolge

```
Phase 1: Static Adapter Checks      ← billigster Einstieg, 7 Tests
         └── conftest.py erweitern (filter_path, filter_source)
         └── test_openwebui_filter.py: Static-Tests

Phase 2: Unit Tests Happy Path     ← Kernfunktionalität
         └── Fixtures: filter_module, fake_post_json, sample_body
         └── test_openwebui_filter.py: inlet/outlet happy path (Tests 1-16)

Phase 3: Unit Tests Fehlerfälle     ← Marktreife: Robustheit
         └── test_openwebui_filter.py: Fehlerfälle (Tests 17-36)

Phase 4: Live Checks erweitern      ← produktives System, non-destructive
         └── test_benchmark_live.py: 2-3 neue OpenWebUI-Tests
         └── live.py: pytest-kompatible Wrapper

Phase 5: E2E-Infrastruktur          ← teuerst, aber höchstes Vertrauen
         └── conftest.py: e2e_mnemlet, e2e_openwebui Fixtures
         └── test_e2e_openwebui_filter.py: 4 Tests
```

Phase 3 ist der **Marktreif-Meilenstein**: Wenn alle Fehlerfälle grün sind, ist der Filter robust genug für Produktion. Phase 4 und 5 sind Sicherheitsnetz und Vertrauensverstärker.

Jede Phase ist abgeschlossen testbar und kann unabhängig commited werden.