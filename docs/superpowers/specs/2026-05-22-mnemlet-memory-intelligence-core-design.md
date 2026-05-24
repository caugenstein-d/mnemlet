# Mnémlet Memory Intelligence Core v0.2 — Design Spec

**Datum:** 2026-05-22  
**Status:** Draft zur Review  
**Projekt:** Mnémlet  
**Repo:** `/home/christoph/mnemlet`  
**Gewählter Ansatz:** Quality Spine MVP  
**Freigabe:** Zielbild, Architektur, Komponenten, Integrationen, Benchmark und Nicht-Ziele wurden im Gespräch bestätigt.

---

## 1. Executive Summary

Mnémlet v0.1 ist ein funktionierender lokaler Memory-Speicher. Es kann speichern, suchen, verfallen lassen und konsolidieren. Für ein marktreifes Werkzeug fehlt aber der eigentliche Gedächtnis-Kern: Mnémlet muss wissen, wann ein Treffer belastbar ist, wann ein alter Fakt nicht mehr aktuell ist und warum ein bestimmter Kontext geliefert wurde.

v0.2 baut deshalb keinen UI-Überbau und keine SaaS-Fantasie. Der **Memory Intelligence Core** wird als **Quality Spine MVP** geschnitten:

1. **Context Pack Builder** — strukturierter Recall statt flacher Trefferliste.
2. **No-Hit / Abstention** — ehrliches „ich weiß es nicht“ statt schwacher Kontext-Injection.
3. **Supersession / Contradiction Handling** — alte, widersprochene Memories bleiben erhalten, werden aber nicht mehr als aktuelle Fakten ausgespielt.
4. **Minimal Provenance** — jedes Ergebnis wird erklärbarer.
5. **Minimal Classifier** — feste Typen, heuristisch, nicht blockierend.
6. **Minimal Policy** — kleine Lifecycle-Regeln statt Policy-Framework.
7. **Review Commands** — remember, forget, replace, confirm als Wartungsgriffe.
8. **OpenWebUI und OpenCode als gleichberechtigte Konsumenten** — Integrationsverträge von Anfang an.
9. **Quality Benchmark MVP** — messbare Gedächtnisqualität, nicht nur Retrieval.

Der Wow-Effekt ist nicht: „Mnémlet hat mehr Features.“  
Der Wow-Effekt ist: **Mnémlet liefert aktuelleren, ehrlicheren und erklärbareren Kontext.**

---

## 2. Kontext und Vorarbeiten

Diese Spec konsolidiert die vorhandenen Entwürfe kritisch:

- `docs/designs/2026-05-22-memory-intelligence-core-v0.2.md`
- `docs/designs/2026-05-22-competitive-analysis.md`
- `docs/superpowers/specs/2026-05-22-openwebui-test-strategy-design.md`
- `docs/superpowers/specs/2026-05-22-quality-benchmark-design.md`
- `docs/superpowers/specs/2026-05-22-trust-security-privacy-layer-design.md`
- ältere Integrationsspecs zu OpenWebUI/OpenCode und Benchmark-Reporting

Die Vorarbeiten enthalten gute Bausteine, aber auch zu viel Breite für einen v0.2-MVP. Diese Spec übernimmt die belastbaren Ideen und entfernt Überbau:

- keine Enterprise-Claims
- keine Cloud-/SaaS-Story
- keine Auth-/Audit-/Secret-Guard-Bündelung in v0.2
- keine Graph-Provenance im MVP
- keine produktiven OpenWebUI-Eingriffe

Bekannter Arbeitsstand beim Start der Designarbeit:

- Branch: `master`
- HEAD: `5b01eab fix: evaluate benchmark expectation fields`
- letzter bekannter Teststand: `122 passed, 15 warnings`
- letzter Quick Benchmark: 48 Queries, `hit_at_3 = 1.0`, `mrr ≈ 0.964`, `adapter_success_rate = 1.0`
- kein GitHub Push bisher
- OpenWebUI darf nicht restarted, killed oder migriert werden

Beim Kontextcheck lagen mehrere neue Design-Artefakte untracked im Repo. Diese Spec ist die konsolidierte Fassung, nicht bloß eine Kopie dieser Entwürfe.

---

## 3. Zielbild

Mnémlet v0.2 soll drei Eigenschaften liefern.

### 3.1 Ehrlich erinnern

Wenn Mnémlet keine belastbaren Treffer hat, soll es das ausdrücken. Schlechte Treffer dürfen nicht als „relevanter Kontext“ in Agentenprompts landen.

Beispiele:

- Query ohne relevante Memories → Abstention `no_relevant_memories`
- nur schwache Scores → Abstention `low_confidence_matches`
- alle Kandidaten wurden weggefiltert → Abstention `all_results_filtered`
- Kandidaten widersprechen sich → Abstention/Flag `contradictory_results`

### 3.2 Aktuell erinnern

Wenn neue Memories alten Informationen widersprechen, darf der alte Stand nicht weiter als aktiver Fakt auftauchen. Die alte Memory bleibt gespeichert und nachvollziehbar, wird aber weich superseded.

Prinzip:

- nicht löschen
- nicht hart überschreiben
- `status='superseded'`
- Link von neuer zu alter Memory
- alter Fakt wird im normalen Recall und in Integrationskontexten nicht ausgespielt

### 3.3 Erklärbar erinnern

Jeder gelieferte Kontext soll minimale Provenance haben:

- Namespace
- Quelle: `vector`, `fts` oder `hybrid`
- Score und Rank
- Memory-Status
- Memory-Typ, falls klassifiziert
- Created-at / Alter
- Access Count
- Policy-/Contradiction-Flags

Das ist noch kein Audit-Log. „Wer hat das wann geschrieben?“ gehört in den Trust/Security/Privacy Layer später. v0.2 erklärt erstmal: **Warum wurde diese Memory geliefert und in welchem Zustand ist sie?**

---

## 4. MVP-Grenze

### 4.1 Muss in v0.2-MVP

| Bereich | Muss rein | Warum |
|---------|-----------|-------|
| Context Pack | Neuer strukturierter Recall-Pfad mit `primary`, `supporting`, optional `superseded` | Agenten brauchen Kontextqualität statt flacher Liste |
| Abstention | No-hit und Low-confidence werden explizit | Verhindert falschen Kontext |
| Supersession | Soft-Supersede bei sicheren Widersprüchen | Alte Fakten dürfen nicht aktiv bleiben |
| Provenance | minimale Ergebnis-Metadaten | Debugging, Benchmark, Erklärbarkeit |
| Classifier | feste Typen, heuristisch, nicht blockierend | Stützt Policies und Supersession |
| Policy | kleine feste Lifecycle-Regeln | Keine Policy-Plattform, nur Schutzlogik |
| Review Commands | remember, forget, replace, confirm | Manuelle Korrektur und Tests |
| OpenWebUI Tests | Unit/Adapter/optional read-only live | zentraler Nutzerkanal |
| OpenCode Tests | Plugin/MCP-Vertrag, Sentinel | gleichberechtigter Nutzerkanal |
| Quality Benchmark | 12–18 synthetische Szenarien | echte Gedächtnisqualität messbar machen |

### 4.2 Nicht im v0.2-MVP

- Auth / API-Key
- Audit Log
- Secret Detection
- Backup / Restore
- RBAC / Multi-User
- Namespace Access Policies
- Policy-Admin-REST-API
- Custom Memory Types
- Graph-basierte Provenance
- UI / Dashboard
- Browser-/Playwright-Tests
- produktive OpenWebUI-E2E-Tests
- LLM-Judge als Release-Gate
- SaaS-/Cloud-/Enterprise-Funktionen

Diese Themen sind nicht falsch. Sie gehören nur nicht in diesen Schnitt.

---

## 5. Architektur

### 5.1 Prinzip

Die bestehende v0.1-Architektur bleibt erkennbar:

- `storage/` — SQLite, ChromaDB, Vault, Embeddings
- `engine/` — Ingest, Recall, Decay, Sleep, LLM
- `server/` — FastAPI, REST-Routen, MCP
- `benchmark/` — Retrieval, Adapter, Live Checks, Reports

v0.2 ergänzt eine neue Schicht:

```text
src/mnemlet/
  intelligence/
    classifier.py      # minimaler Memory-Type
    policy.py          # Lifecycle-/Recall-Regeln
    context_pack.py    # primary/supporting/superseded
    abstention.py      # no-hit/low-confidence
    supersession.py    # contradiction + soft supersede
    provenance.py      # erklärbare Result-Metadaten
    review.py          # remember/forget/replace/confirm
```

Wichtig: Die Intelligence Layer ist kein Paralleluniversum. Sie nutzt vorhandene Engines und erweitert deren Integrationspunkte additiv.

Saubere Architekturformulierung:

> Bestehende v0.1-Endpunkte bleiben kompatibel. Core Engines bleiben konzeptionell stabil, aber `ingest`, `recall`, SQLite und MCP/REST bekommen additive Hooks und Felder.

### 5.2 Bestehende Extension-Seams

Geeignete Stellen im aktuellen Code:

- `src/mnemlet/engine/ingest.py`  
  natürlicher Hook für Klassifikation, Supersession-Kandidaten und metadata enrichment
- `src/mnemlet/engine/recall.py`  
  natürlicher Hook für status filtering, provenance, context-pack input
- `src/mnemlet/storage/sqlite.py`  
  additive Spalten, Statusfilter, Metadata-Updates, Interactions
- `src/mnemlet/server/mcp_server.py`  
  neue MCP-Tools, bestehende Tools bleiben stabil
- `src/mnemlet/server/routes/`  
  neue REST-Routen für Context/Explain/Review
- `src/mnemlet/benchmark/adapters.py` und `live.py`  
  Integrationschecks ohne produktive Eingriffe

### 5.3 Keine Breaking Changes

Bestehende Kontrakte bleiben erhalten:

- `POST /api/v1/ingest` liefert weiter mindestens:
  - `memory_id`
  - `stored`
  - `dedup`
  - `namespace`
  - `retention_score`
  - `chunk_count`
- `POST /api/v1/recall` liefert weiter:
  - `results`
  - `count`
- MCP-Tools `mnemlet_ingest`, `mnemlet_recall`, `mnemlet_search` bleiben nutzbar.

Neue Felder sind additiv. Neue intelligente Semantik kommt über neue Pfade.

---

## 6. Datenmodell

### 6.1 Neue Spalten in `memories`

Additive, nullable/default-safe Erweiterungen:

```sql
ALTER TABLE memories ADD COLUMN memory_type TEXT DEFAULT NULL;
ALTER TABLE memories ADD COLUMN type_confidence REAL DEFAULT NULL;
ALTER TABLE memories ADD COLUMN type_source TEXT DEFAULT NULL;
ALTER TABLE memories ADD COLUMN superseded_by TEXT DEFAULT NULL;
ALTER TABLE memories ADD COLUMN content_summary TEXT DEFAULT NULL;
```

Semantik:

| Feld | Bedeutung |
|------|-----------|
| `memory_type` | einer von `fact`, `preference`, `instruction`, `event`, `context`, oder `NULL` |
| `type_confidence` | heuristische oder LLM-Konfidenz zwischen 0.0 und 1.0 |
| `type_source` | `heuristic`, `llm`, `manual`, oder `NULL` |
| `superseded_by` | ID der neueren Memory, falls diese Memory superseded wurde |
| `content_summary` | kurze Zusammenfassung, optional |

Die Migration darf bestehende Instanzen nicht invalidieren. Falls Spalten bereits existieren, muss die Migration idempotent überspringen.

### 6.2 Neue Statuswerte

Bestehend:

- `active`
- `cold_storage`
- `deleted`

Neu:

- `superseded`
- `forgotten`

Semantik:

| Status | Recall-Verhalten |
|--------|------------------|
| `active` | normal recallbar |
| `cold_storage` | nicht primärer Recall-Stoff |
| `superseded` | standardmäßig ausgefiltert, optional im Context Pack sichtbar |
| `forgotten` | ausgefiltert, wiederherstellbar via Update |
| `deleted` | ausgefiltert |

Normale Recalls und Integrationskontexte dürfen nur `active` als aktuelle Fakten behandeln.

### 6.3 Metadata-Links

Für den MVP werden Links und Flags über `metadata_json` gespeichert:

```json
{
  "supersedes": "old_memory_id",
  "contradicts_with": ["other_memory_id"],
  "supersede_reason": "contradiction",
  "policy_flags": ["supersede_protected"]
}
```

Die vorhandene `graph_edges`-Tabelle bleibt für v0.2-MVP ungenutzt. Sie ist sinnvoll für spätere Graph-Provenance, aber für diesen Schnitt zu groß.

### 6.4 Policy-Konfiguration

Keine `policy_configs`-Tabelle im v0.2-MVP.

Policies sind feste Defaults im Code:

| Typ | Automatisch superseden? | Bemerkung |
|-----|--------------------------|-----------|
| `fact` | ja | bei hoher Contradiction-Confidence |
| `preference` | ja | neue Präferenz darf alte ersetzen |
| `instruction` | nein | nur flaggen, keine automatische Änderung |
| `event` | nein | Ereignisse sind zeitlich, nicht automatisch widersprochen |
| `context` | ja | Umgebungsinfos dürfen aktualisiert werden |
| `NULL` | nein | unbekannter Typ wird konservativ behandelt |

Das hält v0.2 testbar und verhindert ein halbfertiges Policy-Framework.

---

## 7. Komponenten

### 7.1 Minimal Classifier

Aufgabe: Memories typisieren, damit Supersession und Policies nicht blind arbeiten.

MVP-Verhalten:

- deterministische Heuristik zuerst
- keine blockierenden LLM-Calls im Ingest
- LLM-Klassifikation optional/nachgelagert
- manuelle Typvorgabe im MVP über `remember(memory_type=...)`; ein separates Classify-Tool ist später

Feste Typen:

| Typ | Bedeutung | Beispiel |
|-----|-----------|----------|
| `fact` | objektive Information | „Der Service läuft auf Port 4050.“ |
| `preference` | subjektive Präferenz | „Christoph bevorzugt Self-Hosting.“ |
| `instruction` | Regel/Direktive | „OpenWebUI darf nicht restarted werden.“ |
| `event` | zeitgebundenes Ereignis | „Deployment war am 22. Mai.“ |
| `context` | sonstige Umgebung/Situation | „Das Repo liegt unter `/home/christoph/mnemlet`.“ |

Heuristik:

| Muster | Typ |
|--------|-----|
| `bevorzugt`, `prefers`, `mag lieber` | `preference` |
| `immer`, `niemals`, `muss`, `darf nicht`, `never`, `always` | `instruction` |
| Datum-/Terminmarker | `event` |
| technische Aussage mit Ist-/Läuft-/Verwendet-Struktur | `fact` |
| sonst | `context` |

Konfidenzbereiche:

- klare Heuristik: `0.7–0.8`
- schwache Heuristik: `0.5–0.6`
- manuell gesetzt: `1.0`

### 7.2 Minimal Policy Engine

Aufgabe: kleine Lifecycle-Regeln anwenden.

MVP-Regeln:

- Recall filtert standardmäßig nicht-aktive Status aus.
- Automatische Supersession ist nur erlaubt, wenn:
  - Typ-Policy es erlaubt
  - Contradiction-Confidence hoch genug ist
  - beide Memories im selben Namespace liegen
- `instruction` wird nicht automatisch superseded.
- `forgotten`, `deleted`, `superseded` werden nicht in OpenWebUI/OpenCode-Kontext als aktuelle Fakten injiziert.

Keine Access Control. Keine Namespace-Sicherheit. Kein Admin-API.

### 7.3 Supersession / Contradiction Handler

Aufgabe: widersprüchliche Memories erkennen und weich behandeln.

Ingest-Dataflow:

```text
new memory
  -> store as active
  -> classify minimally
  -> find similar active memories in same namespace
  -> contradiction check
  -> policy decision
  -> soft supersede or flag
```

Kandidatensuche:

- gleicher Namespace
- nur `active`
- Top-N ähnliche Memories, MVP-Default: `3`
- bevorzugt gleiche oder kompatible `memory_type`

Contradiction-Entscheidung:

- wenn lokales LLM verfügbar: `llm.detect_contradiction(new, existing)` verwenden
- wenn LLM nicht verfügbar: keine automatische Supersession
- keine mutige Heuristik-Supersession im MVP

Automatische Supersession nur wenn:

```text
contradiction = true
confidence >= 0.8
policy.supersede_on_contradiction = true
```

Aktion bei Auto-Supersession:

- alte Memory: `status='superseded'`
- alte Memory: `superseded_by=<new_id>`
- neue Memory: `metadata_json.supersedes=<old_id>`
- neue Memory: `metadata_json.supersede_reason='contradiction'`
- Interaction: `supersede` oder vergleichbarer Lifecycle-Eintrag

Aktion bei unsicherer oder geschützter Contradiction:

- beide Memories bleiben `active`
- beide bekommen `metadata_json.contradicts_with`
- `policy_flags` enthält z.B. `contradiction_unresolved` oder `supersede_protected`

### 7.4 Context Pack Builder

Aufgabe: Recall-Ergebnisse agentenfreundlich strukturieren.

Neuer Pfad:

- REST: `POST /api/v1/context`
- MCP: `mnemlet_context`

Response-Struktur:

```json
{
  "query": "...",
  "context_pack": {
    "primary": [],
    "supporting": [],
    "superseded": []
  },
  "abstention": null,
  "meta": {
    "total_candidates": 0,
    "pack_size": 0,
    "confidence": 0.0,
    "policy_flags": []
  }
}
```

Gruppierungsregeln:

| Gruppe | Bedingung |
|--------|-----------|
| `primary` | `score >= 0.70` und Status `active` |
| `supporting` | `0.30 <= score < 0.70` und Status `active` |
| `superseded` | Status `superseded`, nur bei `include_superseded=true` |
| ausgeschlossen | `score < 0.30`, `forgotten`, `deleted`, regulär `superseded` |

Die vorherige Inkonsistenz aus dem alten Entwurf wird damit aufgelöst: `primary` beginnt bei `0.70`; `0.30` ist die untere Pack-/Abstention-Grenze, nicht die Primary-Grenze.

### 7.5 Abstention

Aufgabe: schlechte oder fehlende Ergebnisse explizit machen.

Abstention ist kein HTTP-Error. Sie ist ein Feld im Context-Pack.

```json
{
  "reason": "no_relevant_memories",
  "suggestion": "Store or confirm a relevant memory before relying on recall."
}
```

Gründe:

| Grund | Bedingung |
|-------|-----------|
| `no_relevant_memories` | Recall liefert 0 Kandidaten |
| `low_confidence_matches` | höchster Score < `0.30` |
| `all_results_filtered` | Kandidaten existieren, aber alle wurden durch Status/Policy entfernt |
| `contradictory_results` | aktive Ergebnisse enthalten unresolved contradiction flags |

Integrationsregel:

> Bei Abstention injizieren OpenWebUI/OpenCode keinen schwachen Mnémlet-Kontextblock.

### 7.6 Minimal Provenance

Aufgabe: Ergebnisse nachvollziehbar machen.

MVP-Provenance pro Context-Pack-Result:

```json
{
  "source": "vector|fts|hybrid",
  "score": 0.82,
  "rank": 1,
  "namespace": "project",
  "memory_type": "fact",
  "status": "active",
  "created_at": "2026-05-22T10:00:00Z",
  "age_days": 0.4,
  "access_count": 4,
  "policy_flags": []
}
```

Neuer Explain-Pfad:

- REST: `GET /api/v1/explain/{memory_id}`
- MCP: `mnemlet_explain`

MVP-Explain liefert:

- Memory-ID
- Content Preview oder Content, soweit verfügbar
- Namespace
- Status
- Memory Type
- Supersession-Links
- Metadata Flags
- letzte Interaktionen, falls einfach verfügbar

Kein Trust/Audit in v0.2.

### 7.7 Review Commands

Aufgabe: manuelle Memory-Pflege ermöglichen und Lifecycle testbar machen.

MVP-Tools:

| Tool | Zweck | Verhalten |
|------|-------|-----------|
| `mnemlet_remember` | bewusst speichern | optional `memory_type`, kann Dedup umgehen |
| `mnemlet_forget` | bewusst ausblenden | setzt `status='forgotten'`, löscht nicht |
| `mnemlet_replace` | alten Stand ersetzen | alte Memory `superseded`, neue Memory `active`, Link setzen |
| `mnemlet_confirm` | Memory stärken | Retention-Boost, Interaction `confirm` |

Diese Commands sind nicht der Hauptumfang. Sie sind die Wartungsgriffe am Gedächtnis.

---

## 8. API- und MCP-Oberflächen

### 8.1 Bestehende Oberflächen bleiben kompatibel

Keine breaking Änderungen an:

- `POST /api/v1/ingest`
- `POST /api/v1/recall`
- bestehende MCP-Tools

`/api/v1/recall` darf additiv Provenance-Felder in Ergebnissen bekommen, aber bestehende Consumers müssen weiter funktionieren.

### 8.2 Neue REST-Routen

| Route | Methode | Zweck |
|-------|---------|-------|
| `/api/v1/context` | POST | Context Pack für Query |
| `/api/v1/explain/{memory_id}` | GET | Provenance/Status/Links für eine Memory |
| `/api/v1/remember` | POST | explizite Speicherung |
| `/api/v1/forget/{memory_id}` | POST | Status `forgotten` |
| `/api/v1/replace/{memory_id}` | POST | alte Memory superseden, neue speichern |
| `/api/v1/confirm/{memory_id}` | POST | Retention bestätigen/boosten |

`/api/v1/classify/{memory_id}` ist nicht Teil des MVP. Für v0.2 reicht Typisierung über Ingest/Remember und interne Heuristik.

### 8.3 Neue MCP-Tools

| Tool | Zweck |
|------|-------|
| `mnemlet_context` | intelligenter Recall mit Context Pack und Abstention |
| `mnemlet_explain` | Ergebnis/Memory erklären |
| `mnemlet_remember` | bewusst speichern |
| `mnemlet_forget` | bewusst ausblenden |
| `mnemlet_replace` | ersetzen und verlinken |
| `mnemlet_confirm` | bestätigen/boosten |

`mnemlet_classify` ist nicht Teil des MVP. Manuelle Typkorrektur läuft zunächst über `remember(memory_type=...)` oder direkte spätere Wartungsfunktionen.

---

## 9. OpenWebUI- und OpenCode-Strategie

### 9.1 Grundsatz

OpenWebUI ist ein zentraler Nutzerkanal, kein späterer Adapter.

Regeln:

- produktive OpenWebUI-Instanz nicht restarten
- produktive OpenWebUI-Instanz nicht killen
- produktive OpenWebUI-Instanz nicht migrieren
- keine Chat-POSTs gegen Port 8080 in Tests
- read-only Live Checks sind optional und skippen bei Nichterreichbarkeit

### 9.2 Integrationsentscheidung für MVP

Für den MVP wird OpenWebUI nicht sofort hart auf `/api/v1/context` umgestellt.

Stattdessen:

1. Legacy `/api/v1/recall` bleibt stabil und getestet.
2. Ein Context-Pack-Formatter wird testbar vorbereitet.
3. Abstention-/Empty-Verhalten wird im Filter abgesichert.
4. Umschaltung auf `/api/v1/context` passiert bewusst, wenn der neue Pfad stabil ist.

Das ist konservativ, aber richtig. Ein zentraler Nutzerkanal wird nicht nebenbei umverdrahtet.

### 9.3 OpenWebUI-Testpyramide

#### Static/Adapter Checks

- Filter-Datei existiert.
- `Filter.inlet(body, __user__)` existiert.
- `Filter.outlet(body, __user__)` existiert.
- keine hardcoded Secrets.
- Kontext ist bounded.
- Recall-/Context-Endpunkt wird bewusst verwendet.

#### Unit-Tests mit monkeypatched `_post_json`

Kein Netzwerk. Kein OpenWebUI-Service. Kein Mnémlet-Service.

MVP-Fälle:

- inlet injiziert relevante Memories.
- inlet prepended zu bestehender System Message.
- outlet speichert kompakte letzte User/Assistant-Interaktion.
- Mnémlet down → Body unverändert.
- Timeout → Body unverändert.
- malformed response → Body unverändert.
- empty results → keine Injection.
- Abstention → keine Injection.
- superseded Memories → nicht als aktuelle Fakten injizieren.
- outlet leakt nicht die gesamte Historie.

#### Non-destructive Live Checks

Optional, read-only:

- `GET /_app/version.json`
- optional `GET /api/v1/functions/`, falls ohne sensible Auth machbar
- `pytest.skip`, wenn OpenWebUI nicht erreichbar ist

Keine POSTs. Keine Schreiboperationen. Keine Service-Manipulation.

#### Isoliertes E2E später

Nicht MVP-blockierend.

- OpenWebUI Testinstanz auf Port `8081`
- Mnémlet Testinstanz auf Port `4051`
- `@pytest.mark.e2e`
- Default-Pytest führt diese Tests nicht aus

### 9.4 OpenCode-Teststrategie

OpenCode bleibt gleichberechtigt.

MVP-Fälle:

- statischer Plugin-Check bleibt.
- System-Prompt-Transform enthält bounded Context.
- Sentinel `Nebelkrähe` bleibt Testanker.
- Abstention erzeugt keinen nutzlosen Kontextblock.
- Context-Pack-Formatter wird separat testbar.
- Live `opencode run` bleibt opt-in.

### 9.5 Gemeinsamer Integrationsvertrag

Für beide Kanäle gilt:

- kein Kontextblock bei Abstention
- kein Kontextblock nur aus `superseded`/`forgotten`/`deleted`
- Kontextlänge bounded
- Legacy Recall bleibt nutzbar
- neue Context Packs werden bewusst und getestet adaptiert

---

## 10. Quality Benchmark MVP

### 10.1 Ziel

Der bestehende 48-Query-Benchmark misst Retrieval. v0.2 braucht zusätzlich Gedächtnisqualität:

- Weiß Mnémlet, wann es nichts weiß?
- Veraltet ein neuer Fakt den alten?
- Wird OpenWebUI vor falschem Kontext geschützt?
- Sind Ergebnisse erklärbar?

### 10.2 Umfang

MVP statt Vollausbau:

- 12–18 synthetische Szenarien
- 2–3 pro Kernkategorie
- deterministic assertions only
- kein externer/cloud-basierter LLM-Judge im Pass/Fail
- automatische Contradiction-Checks werden in zwei Profilen bewertet: Pipeline-Tests mit Fake-Detector sind blocking; echte lokale LLM-Checks sind ein separates optionales Profil
- public dataset commit-safe
- private Daten bleiben außerhalb

Kategorien:

```text
uncertainty_gating
contradiction_handling
fact_evolution
agent_context_assembly
provenance_tracking
openwebui_integration_quality
opencode_integration_quality
```

### 10.3 Beispiel-Szenarien

#### No-Hit / Abstention

```text
Given namespace devops contains only cooking/garden distractors
When query asks for CI/CD deployment pipeline
Then context response has abstention.reason = low_confidence_matches or no_relevant_memories
And no primary/supporting results are injected
```

#### Supersession

```text
Given memory A says service runs on port 8080
And memory B says service now runs on port 9090
When contradiction check is confident
Then A status is superseded
And B is active
And normal recall returns B, not A
```

#### OpenWebUI Abstention

```text
Given filter inlet receives a context response with abstention
When inlet runs
Then body is returned without Mnémlet system context
```

#### Provenance

```text
Given a context result is returned
Then it includes namespace, source, score, rank, status and created_at
```

### 10.4 Release Gates

Bestehende Tests:

- pytest bleibt grün.
- Quick Benchmark regressiert nicht hart:
  - `hit_at_3 >= 0.95`
  - `adapter_success_rate = 1.0`

Quality-MVP:

Blocking deterministic gates:

| Metrik | Schwelle |
|--------|----------|
| `empty_correct_rate` | `>= 0.67` |
| `false_positive_rate` für No-Hit | `<= 0.33` |
| `replace_supersession_rate` | `= 1.0` |
| `provenance_completeness` | `>= 0.95` |
| OpenWebUI unit/adapter success | `1.0` |
| OpenCode adapter success | `1.0` |

Detector-enabled gates:

| Metrik | Schwelle | Gilt wann? |
|--------|----------|------------|
| `contradiction_pipeline_rate` | `= 1.0` | mit Fake-Detector in Tests |
| `auto_contradiction_resolution_rate` | `>= 0.60` | wenn lokaler LLM-Detector für Release-Profil aktiviert ist |

Diese Gates sind bewusst streng genug, um Qualität zu erzwingen, aber nicht so großspurig wie externe SOTA-Claims.

---

## 11. Akzeptanzkriterien

### 11.1 Context Pack

- `mnemlet_context` liefert `primary`, `supporting`, `superseded`.
- Ergebnisse unter Score `0.30` werden nicht in den Pack aufgenommen.
- `primary` beginnt bei Score `0.70`.
- Output ist bounded.
- Legacy `mnemlet_recall` bleibt kompatibel.

### 11.2 Abstention

- 0 Kandidaten → `abstention.reason = "no_relevant_memories"`.
- höchster Score < `0.30` → `abstention.reason = "low_confidence_matches"`.
- alle Kandidaten ausgefiltert → `abstention.reason = "all_results_filtered"`.
- aktive unresolved contradictions → `abstention.reason` oder `policy_flags` zeigt `contradictory_results`.
- OpenWebUI/OpenCode injizieren bei Abstention keinen Kontextblock.

### 11.3 Supersession

- Alte Memory bleibt gespeichert.
- Alte Memory bekommt `status='superseded'`.
- Alte Memory bekommt `superseded_by=<new_id>`.
- Neue Memory bekommt `metadata_json.supersedes=<old_id>`.
- Normaler Recall liefert alte Memory nicht als active fact.
- Manuelles `replace` erfüllt die Supersession-Pipeline deterministisch.
- Automatische Supersession passiert nur bei Confidence `>= 0.8` und erlaubender Policy.
- Automatische Contradiction wird blocking mit Fake-Detector getestet und separat mit lokalem LLM-Profil gemessen.
- `instruction` wird nicht automatisch superseded.

### 11.4 Provenance

- Jedes Context-Pack-Ergebnis hat mindestens:
  - `namespace`
  - `source`
  - `score`
  - `rank`
  - `status`
  - `created_at`
- Explain-Pfad zeigt Status, Typ, Supersession-Links und Metadata Flags.

### 11.5 Review Commands

- `remember` speichert bewusst und optional mit `memory_type`.
- `forget` setzt `status='forgotten'` und löscht nicht.
- `replace` setzt alte Memory auf `superseded` und verlinkt neue Memory.
- `confirm` erhöht Retention und protokolliert eine Interaction.

### 11.6 Integrationen

- OpenWebUI Unit-Tests laufen ohne OpenWebUI-Service und ohne Netzwerk.
- OpenWebUI Fehlerfälle geben Body unverändert zurück.
- OpenWebUI injiziert nichts bei Abstention/Empty.
- OpenWebUI testet, dass superseded nicht als current fact injiziert wird.
- OpenCode Plugin-/Adaptertests bleiben grün.
- Live Checks sind optional und non-destructive.

---

## 12. Implementierungsreihenfolge für den späteren Plan

Noch kein Produktivcode ohne freigegebene Spec. Nach Review sollte der Implementierungsplan in dieser Reihenfolge entstehen:

1. **Contract Tests zuerst**
   - Legacy Recall/Ingest kompatibel
   - OpenWebUI/OpenCode Adapter bleiben grün
   - neue erwartete Abstention-/Supersession-Fälle als failing tests

2. **Datenmodell additiv**
   - nullable Felder
   - neue Statuswerte
   - idempotente Migration

3. **Provenance im Recall**
   - Source/Score/Rank/Status sichtbar machen
   - Legacy-Response nicht brechen

4. **Context Pack + Abstention**
   - `/api/v1/context`
   - `mnemlet_context`
   - keine Filter-Umschaltung erzwingen

5. **Minimal Classifier + Policy**
   - deterministisch/heuristisch
   - keine blockierenden LLM-Calls

6. **Supersession**
   - manuelles `replace` zuerst
   - automatische Contradiction konservativ
   - LLM nur bei hoher Confidence

7. **Review Commands**
   - remember/forget/replace/confirm
   - klein, testbar

8. **OpenWebUI/OpenCode Context-Pack-Kompatibilität**
   - Formatter
   - Abstention-Verhalten
   - keine schwache Injection

9. **Quality Benchmark MVP**
   - 12–18 Szenarien
   - Reports
   - Release-Gates

Der kritische Pfad ist:

```text
Status/Provenance -> Context Pack -> Abstention -> Supersession -> Integration contracts -> Quality benchmark
```

Nicht der Classifier. Der ist Stütze, nicht Hauptdarsteller.

---

## 13. Risiken und Gegenmaßnahmen

| Risiko | Wahrscheinlichkeit | Auswirkung | Gegenmaßnahme |
|--------|--------------------|------------|---------------|
| Scope Creep in Policy Engine | hoch | hoch | keine `policy_configs` im MVP, feste Regeln |
| LLM hängt Ingest auf | mittel | hoch | keine blockierende LLM-Pflicht, Heuristik zuerst |
| False-positive Supersession | mittel | hoch | Auto nur bei Confidence `>= 0.8`, `instruction` geschützt |
| OpenWebUI Regression | mittel | hoch | Unit-/Adaptertests vor Umschaltung, kein produktiver Restart |
| Legacy API Break | mittel | hoch | neue Pfade additiv, alte Response Keys bleiben |
| Benchmark wird zu groß | mittel | mittel | MVP 12–18 Szenarien, kein LLM-Judge-Gate |
| Provenance aus Chroma/FTS inkonsistent | mittel | mittel | Recall-Merge muss Source/Rank explizit behalten |
| Statusfilter übersieht Chroma-Treffer | hoch | hoch | Recall muss SQLite-Status nach Vector-Suche validieren |

---

## 14. Rollback- und Sicherheitsplan

Da v0.2 additive Felder und neue Routen nutzt, ist Rollback überschaubar:

- Legacy `recall` und `ingest` bleiben primäre Rückfallpfade.
- OpenWebUI bleibt zunächst auf Legacy Recall.
- Neue Context-Pack-Nutzung wird nur bewusst aktiviert.
- Supersession löscht keine Daten; alte Memories bleiben wiederherstellbar.
- `forgotten` löscht keine Daten; Status kann auf `active` zurückgesetzt werden.
- Migrationen sind additive `ADD COLUMN`-Operationen und dürfen keine Daten entfernen.
- Bei Problemen kann die Intelligence-Nutzung abgeschaltet werden, ohne bestehende v0.1-Daten zu verlieren.

Vor produktiver Aktivierung muss ein DB/Vault/Chroma-Backup außerhalb dieser Spec eingeplant werden. Backup/Restore selbst ist aber nicht Teil von v0.2-MVP.

---

## 15. Implementierungsentscheidungen, die diese Spec festlegt

Damit der spätere Plan nicht wieder ins Schwimmen gerät, legt diese Spec folgende Defaults fest:

1. `/api/v1/classify/{memory_id}` und `mnemlet_classify` sind nicht Teil des MVP.
2. `mnemlet_context` baut auf dem bestehenden `RecallEngine` auf. Der Recall-Pfad wird intern provenance-fähig erweitert, statt einen zweiten Suchalgorithmus zu bauen.
3. Source-Provenance wird im Merge-Schritt erhalten: Vector-only, FTS-only oder Hybrid müssen bis in Context Pack und Explain sichtbar bleiben.
4. Die erste OpenWebUI-Testscheibe ist klein: empty/abstention/no-injection plus malformed/down/timeout. Erst danach kommt Context-Pack-Formatting.
5. Der Quality Benchmark bekommt einen minimalen eigenen Quality-Runner im bestehenden `benchmark/`-Kontext. Failing pytest-Szenarien dürfen die TDD-Schritte treiben, aber v0.2 ist erst fertig, wenn die Quality-Szenarien auch über den Benchmark-Pfad berichtbar sind.

Diese Entscheidungen sind absichtlich pragmatisch. Sie halten den MVP schmal, ohne die Benchmarkbarkeit zu opfern.

---

## 16. Review-Checkliste

Vor Implementation muss Christoph diese Spec reviewen und freigeben.

Review-Fragen:

1. Ist die MVP-Grenze hart genug?
2. Ist OpenWebUI ausreichend früh und sicher integriert?
3. Sind Auth/Audit/Secret/Backup zurecht später?
4. Sind die Release-Gates realistisch für den Pi?
5. Ist der kritische Pfad richtig priorisiert?

Nach Freigabe folgt ein separater Implementierungsplan mit TDD-Schritten.
