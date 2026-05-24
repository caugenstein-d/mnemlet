# Memory Intelligence Core — v0.2 Design

**Datum:** 2026-05-22  
**Status:** Draft  
**Autor:** Mira (Research & Systems-Design)  
**Projekt:** Mnémlet  

---

## Executive Summary

Mnémlet v0.1 ist ein funktionierender, aber *dummer* Memory-Speicher: Er kann Erinnerungen speichern und abrufen, aber er weiß nicht, **was** er speichert, **warum** etwas wichtig ist, **ob** sich Dinge widersprechen, oder **woher** ein Ergebnis kommt. Ein Agent kann nicht aktiv mit seinen Erinnerungen arbeiten — er kann nichts vergessen, nichts bestätigen, nichts ersetzen.

Der **Memory Intelligence Core** (v0.2) macht Mnémlet von einem passiven Speicher zu einem aktiven Gedächtnis durch sieben Komponenten:

1. **Memory Classifier** — Typisierung jeder Erinnerung (fact/preference/instruction/event/context)
2. **Memory Policy Engine** — Typ-basierte Regeln für Retention, Access und Lifecycle
3. **Context Pack Builder** — Strukturierte Ergebnis-Assembly für Agenten-Queries
4. **No-Hit / Abstention Logic** — Ehrliches "Weiß ich nicht" statt schlechter Ergebnisse
5. **Supersession / Contradiction Handler** — Saubere Behandlung widersprüchlicher Erinnerungen
6. **Provenance / Explainability** — Nachvollziehbarkeit warum etwas geliefert wurde
7. **Review Commands** — Aktive Steuerung: remember, forget, replace, confirm

### Architektur-Entscheidungen

| Entscheidung | Wahl | Begründung |
|-------------|------|------------|
| Intelligenz-Modell | LLM-gestützt (Ollama) | Beste Klassifikations- und Contradiction-Qualität, bestehendes `llm.py` |
| Context Pack Scope | Ergebnis-Assembler | Agent entscheidet selbst über Nutzung, kein Prompt-Generator |
| Schnittstelle | Dedizierte MCP-Tools | Saubere Semantik, keine Überladung bestehender Endpunkte |
| Supersession-Strategie | Soft-Supersede | Alte Erinnerung bleibt, wird nur nicht mehr im Recall gezeigt |
| Klassifikations-Typen | Feste 5 Typen | Vorhersagbar, filterbar, kein Label-Chaos |
| Architektur-Ansatz | Layered Intelligence | Keine Modifikation bestehender Engines, saubere Schichtentrennung |

---

## Problem das gelöst wird

Mnémlet v0.1 hat fundamentale Lücken in der Gedächtnis-Intelligenz:

| Lücke | Auswirkung |
|-------|-----------|
| Keine Typisierung | Agent kann nicht nach Art der Information filtern (Fakten vs. Präferenzen vs. Instruktionen) |
| Keine Policies | Alle Memories gleichbehandelt — eine wichtige Instruktion verfällt genauso wie ein flüchtiger Kontext |
| Kein Context Pack | Recall liefert eine flache Liste ohne Struktur, Gruppierung oder Erklärungen |
| Kein Abstention | Bei schlechten Ergebnissen wird trotzdem etwas geliefert — Agent kann nicht unterscheiden |
| Kein Widerspruch-Handling | Neue Info kann alte widersprechen, beide bleiben aktiv und verwirren |
| Keine Provenance | Agent weiß nicht, warum ein Ergebnis geliefert wurde oder wie vertrauenswürdig es ist |
| Keine Review-Commands | Agent kann nichts aktiv vergessen, bestätigen oder ersetzen |

---

## Architektur: Layered Intelligence

```
┌──────────────────────────────────────────────────┐
│                 Intelligence Layer                 │
│                                                   │
│  ┌─────────────┐ ┌──────────────┐ ┌────────────┐ │
│  │ Classifier  │ │ Policy Engine│ │ Context Pack│ │
│  │             │ │              │ │  Builder   │ │
│  └─────────────┘ └──────────────┘ └────────────┘ │
│  ┌──────────────┐ ┌────────────────┐ ┌─────────┐ │
│  │ Abstention   │ │ Supersession/   │ │Review   │ │
│  │ Logic        │ │ Contradiction   │ │Commands │ │
│  └──────────────┘ └────────────────┘ └─────────┘ │
│  ┌──────────────────────────────────────────────┐ │
│  │ Provenance / Explainability                  │ │
│  └──────────────────────────────────────────────┘ │
├──────────────────────────────────────────────────┤
│                 Core Engine Layer                  │
│                                                   │
│  ┌──────────┐ ┌──────────┐ ┌───────┐ ┌───────┐  │
│  │ Ingest   │ │  Recall  │ │ Decay │ │ Sleep │  │
│  │ Engine   │ │  Engine  │ │Engine │ │Engine │  │
│  └──────────┘ └──────────┘ └───────┘ └───────┘  │
├──────────────────────────────────────────────────┤
│                 Storage Layer                     │
│                                                   │
│  ┌──────────┐ ┌──────────┐ ┌───────┐ ┌─────────┐ │
│  │ SQLite   │ │ ChromaDB │ │ Vault │ │ ONNX    │ │
│  │          │ │          │ │       │ │Embeds   │ │
│  └──────────┘ └──────────┘ └───────┘ └─────────┘ │
└──────────────────────────────────────────────────┘
```

**Prinzip:** Die Intelligence Layer ruft die Core Engines auf, erweitert deren Ergebnisse, füllt Metadaten nach — aber modifikator bestehende Engines nicht. Neue Funktionalität kommt als neue Module in der Intelligence Layer.

---

## Komponenten

### 1. Memory Classifier

**Verantwortlichkeit:** Jede neue Erinnerung bei Ingest mit Typ und Metadaten anreichern.

**Feste Typen:**

| Typ | Bedeutung | Beispiel |
|-----|-----------|---------|
| `fact` | Objektive Information | "Python 3.12 wurde im Oktober 2023 released" |
| `preference` | Subjektive Präferenz | "Christoph bevorzugt Self-Hosting" |
| `instruction` | Direktive, Regel | "Nimm nie externe APIs" |
| `event` | Zeitgebundenes Ereignis | "Deployment am 15. Mai um 14:00" |
| `context` | Umgebungs-, Situationsinfo | "Projekt läuft auf einem Pi 5 mit 16GB" |

**Ablauf:**
1. `IngestEngine.ingest()` speichert die Erinnerung wie bisher — blockierend, sofort
2. Intelligence Layer ruft asynchron `Classifier.classify(content, namespace)` via LLM auf
3. Ergebnis wird in `memories` geschrieben: `memory_type`, `type_confidence`, `type_source`, `content_summary`
4. **Fallback** wenn LLM nicht verfügbar: `memory_type=NULL`, `type_source=NULL`. Nächster Sleep-Zyklus klassifiziert nach.

**LLM-Prompt:**
```
System: Classify this memory into exactly one type: fact, preference, instruction, event, context.
Respond in JSON: {"type": "...", "confidence": 0.0-1.0, "summary": "one-line summary"}

Memory: {content}
Namespace: {namespace}
```

**Heuristik-Fallback** (wenn kein LLM):
- Enthält "bevorzugt"/"bevorzuge"/"prefers" → `preference`
- Enthält "immer"/"niemals"/"muss"/"darf nicht" → `instruction`
- Enthält Datumsangabe → `event`
- Default: `context`

**Asynchronitätsgarantie:** Der Ingest-Call returnt sofort. Klassifikation läuft asynchron und reichert nach. Kein Ingest-Call blockiert wegen LLM-Latenz.

**Asynchronität-Modi:** Klassifikation und Contradiction-Check haben zwei Ausführungspfade:
1. **Sofort-Background:** Wenn das LLM erreichbar ist, wird die Klassifikation in einem Background-Task gestartet (FastAPI BackgroundTasks).
2. **Sleep-Nachholung:** Wenn das LLM nicht erreichbar war, klassifiziert der nächste Sleep-Zyklus alle `memory_type=NULL`-Memories nach.

### 2. Memory Policy Engine

**Verantwortlichkeit:** Typ-basierte Regeln für Retention, Access und Lifecycle.

**Default-Policies (pro Namespace + Typ konfigurierbar):**

| Policy | fact | preference | instruction | event | context |
|--------|------|-----------|-------------|-------|---------|
| `min_retention_score` | 0.10 | 0.05 | 0.30 | 0.02 | 0.02 |
| `max_age_days` | — | — | — | 365 | 90 |
| `supersede_on_contradiction` | true | true | false | false | true |
| `require_confirmation_for_delete` | false | false | true | false | false |

**Ablauf:**
- **Bei Ingest:** Policy bestimmt, ob eine Memory besondere Behandlung braucht (z.B. `instruction` → keine automatische Supersession)
- **Bei Recall:** Policy filtert `superseded`-Memories aus, markiert `require_confirmation`-Memories
- **Bei Decay:** Policy überschreibt die globalen `purge_threshold`-Werte pro Typ (Instruktionen werden nicht so schnell gepurget)

**Speicherung:** `policy_configs`-Tabelle in SQLite. Defaults硬kodiert in `constants.py`, überschreibbar per API.

### 3. Context Pack Builder

**Verantwortlichkeit:** Strukturierte, agent-freundliche Ergebniszusammenstellung aus einem Recall liefern.

**Ausgabe-Struktur:**
```python
{
    "query": "Christophs Hosting-Präferenzen",
    "context_pack": {
        "primary": [      # Score >= 0.7, direkt relevant
            {
                "id": "abc123",
                "content": "Christoph bevorzugt Self-Hosting",
                "type": "preference",
                "score": 0.92,
                "provenance": {
                    "source": "hybrid",
                    "decay_adjusted_score": 0.88,
                    "hit_rank": 1,
                    "age_days": 12.5,
                    "access_count": 3
                }
            }
        ],
        "supporting": [   # Score 0.3–0.7, kontextuell verwandt
            {
                "id": "def456",
                "content": "Projekt läuft auf Pi 5 mit 16GB",
                "type": "context",
                "score": 0.55
            }
        ],
        "superseded": [   # Ersetzte Erinnerungen zum Überblick
            {
                "id": "old789",
                "content": "Christoph nutzt Ubuntu",
                "type": "fact",
                "superseded_by": "new101",
                "superseded_reason": "contradiction"
            }
        ]
    },
    "abstention": None,  # oder {"reason": "...", "suggestion": "..."}
    "meta": {
        "total_candidates": 15,
        "pack_size": 4,
        "types_included": ["preference", "context"],
        "confidence": 0.85,
        "policy_flags": []
    }
}
```

**Gruppierungs-Regeln:**
- `primary`: Score >= 0.7 ODER Confidence >= 0.8 und Score >= 0.5
- `supporting`: Score 0.3–0.7 und nicht in primary
- `superseded`: Status `superseded`, nur wenn `include_superseded=true`

**Reihenfolge:** Innerhalb jeder Gruppe nach Score absteigend.

### 4. No-Hit / Abstention Logic

**Verantwortlichkeit:** Ehrliche Kommunikation wenn keine guten Ergebnisse da sind.

**Abstention-Regeln (priorisiert):**

| Bedingung | Abstention-Grund | Suggestion |
|-----------|-----------------|------------|
| Recall liefert 0 Ergebnisse | `no_relevant_memories` | "Use mnemlet_remember to store this information" |
| Höchster Score < 0.3 | `low_confidence_matches` | "Results may not be relevant. Consider rephrasing or storing related information." |
| Alle Ergebnisse sind `superseded` | `all_superseded` | "All results have been superseded. See superseded list for current versions." |
| Ergebnisse widersprechen sich | `contradictory_results` | "Results contain contradictions. Use mnemlet_explain for details." |

**Keine Abstention** wenn mindestens ein primary-Ergebnis mit Score >= 0.3 existiert.

**Abstention wird im Context Pack als Feld zurückgegeben, nicht als Error.** Der Agent kann entscheiden, ob er die Ergebnisse trotzdem nutzt.

### 5. Supersession / Contradiction Handler

**Verantwortlichkeit:** Widersprüchliche Erinnerungen erkennen und sauber handhaben.

**Prozess:**

```
Neuer Inhalt arrives
    │
    ▼
Recall top 3 ähnliche Memories im selben Namespace
    │
    ▼
Für jede: LLM detect_contradiction(new, existing)
    │
    ├── Kein Widerspruch → keine Aktion
    │
    └── Widerspruch erkannt
         │
         ▼
    Policy.pr_check(namespace, memory_type)
         │
         ├── supersede_on_contradiction = true
         │    → Alte Memory: status='superseded'
         │    → Neue Memory: metadata_json.supersedes=old_id
         │    → interactions: type='supersede'
         │
         └── supersede_on_contradiction = false
              → Beide bleiben active
              → Beide bekommen metadata_json.contradicts_with=[other_id]
              → interactions: type='contradiction_detected'
```

**Confidence-Schwelle:** Automatische Supersession nur wenn LLM `contradiction=true` mit `confidence >= 0.8`. Darunter nur Flaggung, keine Aktion.

**Transparenz:** Jede Supersession wird in `interactions` mit `type='supersede'` protokolliert, inkl. Begründung.

### 6. Provenance / Explainability

**Verantwortlichkeit:** Nachvollziehbarkeit — warum wurde ein Ergebnis geliefert?

**Provenance-Struktur (in jedem Context-Pack-Ergebnis):**
```python
{
    "source": "hybrid",              # "vector", "fts", oder "hybrid"
    "score": 0.92,                    # Original-Hybrid-Score
    "decay_adjusted_score": 0.88,     # Score nach Decay-Anpassung
    "original_rank": 1,               # Position im Original-Recall
    "type": "preference",
    "age_days": 12.5,
    "access_count": 3,
    "superseded_by": None,
    "policy_flags": [],
    "interactions_summary": {
        "total": 5,
        "last_interaction": "recall",
        "last_interaction_at": "2026-05-20T14:30:00Z"
    }
}
```

**Explain-Tool:** `mnemlet_explain(memory_id)` liefert:
1. Volle Provenance-Struktur
2. Interaktions-History (letzte 10)
3. Verde von Supersession/Contradiction falls zutreffend
4. Policy-Status (welche Policies greifen)

### 7. Review Commands

**Zwei Arten von Review:**

**Aktiv (neue MCP-Tools):**

| Tool | Parameter | Beschreibung |
|------|-----------|-------------|
| `mnemlet_remember` | `content, namespace, importance, memory_type` | Explizite Speicherung. Kein Dedup-Filter. Immer `stored: true`. Typ kann vorgegeben werden. |
| `mnemlet_forget` | `memory_id` | Setzt `status='forgotten'`. Rückholbar. |
| `mnemlet_replace` | `memory_id, new_content, importance` | Alte → `superseded`, neue → `active` mit Verknüpfung. |
| `mnemlet_confirm` | `memory_id` | Bestätigung. Retention += 0.20. Interaction `confirm`. |

**Intelligent (neues MCP-Tool):**

| Tool | Parameter | Beschreibung |
|------|-----------|-------------|
| `mnemlet_context` | `query, namespace, limit, include_superseded` | Liefert Context Pack. Das primäre Recall-Tool für Agenten. |
| `mnemlet_explain` | `memory_id` | Provenance-Kette für eine Memory. |
| `mnemlet_classify` | `memory_id, memory_type` | Manuelles (Re-)Klassifizieren oder Typ-Korrektur. |

**Beispiel `mnemlet_replace`:**
```json
// Input
{
    "memory_id": "abc123",
    "new_content": "Christoph bevorzugt oder-clause statt copyleft",
    "importance": 0.7
}

// Output
{
    "old_id": "abc123",
    "old_status": "superseded",
    "new_id": "def456",
    "new_memory": {
        "id": "def456",
        "content_preview": "Christoph bevorzugt oder-clause statt copyleft",
        "memory_type": "preference",
        "retention_score": 0.55,
        "metadata": {
            "supersedes": "abc123"
        }
    }
}
```

---

## Datenmodell-Erweiterungen

### Neue Spalten in `memories`

```sql
ALTER TABLE memories ADD COLUMN memory_type TEXT DEFAULT NULL;
ALTER TABLE memories ADD COLUMN type_confidence REAL DEFAULT NULL;
ALTER TABLE memories ADD COLUMN type_source TEXT DEFAULT NULL;  -- 'llm' oder 'heuristic'
ALTER TABLE memories ADD COLUMN superseded_by TEXT DEFAULT NULL;
ALTER TABLE memories ADD COLUMN content_summary TEXT DEFAULT NULL;
```

| Spalte | Typ | Default | Beschreibung |
|--------|-----|---------|-------------|
| `memory_type` | `TEXT` | `NULL` | fact, preference, instruction, event, context. NULL bis klassifiziert. |
| `type_confidence` | `REAL` | `NULL` | 0.0–1.0, LLM-Konfidenz. |
| `type_source` | `TEXT` | `NULL` | `llm` oder `heuristic`. |
| `superseded_by` | `TEXT` | `NULL` | ID der neueren Erinnerung. |
| `content_summary` | `TEXT` | `NULL` | Einzeilige Zusammenfassung vom LLM. |

**Wichtig:** Alle neuen Spalten sind `DEFAULT NULL`. Bestehende Daten werden nicht invalidiert. Migration ist reines `ADD COLUMN`.

### Neue Tabelle: `policy_configs`

```sql
CREATE TABLE IF NOT EXISTS policy_configs (
    namespace TEXT NOT NULL,
    memory_type TEXT NOT NULL,
    min_retention_score REAL DEFAULT 0.05,
    max_age_days INTEGER,                          -- NULL = kein Limit
    supersede_on_contradiction INTEGER DEFAULT 0,  -- SQLite boolean
    require_confirmation INTEGER DEFAULT 0,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (namespace, memory_type)
);
```

### Neue Interaktionstypen

| Typ | Beschreibung |
|-----|-------------|
| `classify` | Memory wurde typisiert |
| `supersede` | Memory A hat Memory B supersedet |
| `contradiction_detected` | Widerspruch erkannt (keine automatische Supersession) |
| `confirm` | Memory wurde manuell bestätigt |
| `forget` | Memory wurde vergessen-markiert |
| `replace` | Memory wurde ersetzt |
| `abstention` | Recall hat Abstention geliefert |

### Neuer Memory-Status: `forgotten`

Zusätzlich zu `active`, `cold_storage`, `deleted` kommt `forgotten`:
- Explizit vergessen via `mnemlet_forget`
- Wiederherstellbar via `mnemlet_update(status='active')`
- Wird im Recall *nicht* zurückgegeben (wie `superseded`)
- Wird vom Decay-Prozess *nicht* gepurged (nicht `deleted`)
- `forgotten` ist ein bewusstes Status-Tag, kein Zwischenstadium

### Erweiterung von `metadata_json`

Neue optionale Keys:

```json
{
    "supersedes": "old_memory_id",
    "contradicts_with": ["id1", "id2"],
    "policy_flags": ["supersede_protected"],
    "type_details": {
        "subtype": null,
        "entities": ["Python", "Self-Hosting"]
    },
    "supersede_reason": "contradiction"
}
```

---

## Beispiel-Workflows

### Workflow 1: Ingest mit Klassifikation (kein Widerspruch)

```
Agent → mnemlet_ingest("Christoph nutzt Ubuntu auf dem Pi")

1. IngestEngine.ingest()
   → chunk, dedup, embed, store
   → Rückgabe: {memory_id: "abc123", stored: true}

2. Intelligence.classify() [asynchron]
   → LLM → type="fact", confidence=0.91, summary="Christoph uses Ubuntu on Pi"
   → UPDATE memories SET memory_type='fact', type_confidence=0.91,
     type_source='llm', content_summary='...'

3. Intelligence.check_contradictions()
   → Recall top 3 im namespace
   → Kein Widerspruch → keine Aktion

4. Final state: memory_type=fact, keine Verknüpfungen
```

### Workflow 2: Ingest mit Contradiction

```
Agent → mnemlet_ingest("Christoph nutzt Arch Linux auf dem Pi")

1. IngestEngine.ingest()
   → Speichern als neue Memory

2. Intelligence.classify()
   → LLM → type="fact"

3. Intelligence.check_contradictions()
   → Recall findet "Christoph nutzt Ubuntu auf dem Pi" (score: 0.78)
   → LLM detect_contradiction → {contradiction: true, confidence: 0.95}

4. Policy.pr_check("default", "fact")
   → supersede_on_contradiction = true

5. Alte Memory:
   → status = 'superseded'
   → superseded_by = <new_id>
   → interactions: type='supersede'

6. Neue Memory:
   → metadata_json.supersedes = <old_id>
   → metadata_json.supersede_reason = 'contradiction'

7. Rückgabe: {
     memory_id: "...",
     stored: true,
     contradiction_detected: true,
     superseded_ids: ["old_id"]
   }
```

### Workflow 3: Context Pack Recall

```
Agent → mnemlet_context(query="Christophs Hosting-Präferenzen", namespace="default")

1. RecallEngine.recall()
   → Hybrid search, top 15

2. Intelligence.build_context_pack(results, query)
   a. Filtere superseded → in "superseded" Gruppe
   b. Gruppiere: score >= 0.7 → primary, 0.3–0.7 → supporting
   c. Füge Provenance hinzu
   d. Prüfe Abstention-Bedingungen

3. Rückgabe: Context Pack Struktur (siehe Abschnitt 3)
```

### Workflow 4: No-Hit Abstention

```
Agent → mnemlet_context(query="Christophs Lieblingskaffeemarke")

1. RecallEngine.recall() → 0 Ergebnisse

2. Intelligence.check_abstention([])
   → abstention: {reason: "no_relevant_memories",
                   suggestion: "Use mnemlet_remember to store this information"}

3. Rückgabe: {
     context_pack: {primary: [], supporting: [], superseded: []},
     abstention: {reason: "no_relevant_memories", suggestion: "..."},
     meta: {total_candidates: 0, pack_size: 0, types_included: [],
            confidence: 0.0}
   }
```

### Workflow 5: Review — Ersetzen

```
Agent → mnemlet_replace(memory_id="abc123",
                        new_content="Christoph bevorzugt ARM-Architektur")

1. Prüfe memory_id existiert und ist active
2. Intelligence.classify(new_content) → type="preference"
3. IngestEngine.ingest(new_content) mit Typ und Verknüpfung
4. Alte Memory: status='superseded', superseded_by=<new_id>
5. interactions: type='replace', memory_id=old, metadata={new_id: ...}

6. Rückgabe: {
     old_id: "abc123",
     old_status: "superseded",
     new_id: "def456",
     new_memory: {id: "def456", content_preview: "...", memory_type: "preference", ...}
   }
```

---

## API / MCP-Kommandos

### Neue MCP-Tools

| Tool | Parameter | Rückgabe | Beschreibung |
|------|-----------|----------|-------------|
| `mnemlet_remember` | `content, namespace?, importance?, memory_type?` | Wie `mnemlet_ingest` + `memory_type` | Explizite Speicherung, kein Dedup |
| `mnemlet_forget` | `memory_id` | `{status: "forgotten", memory_id: "..."}` | Setzt status=forgotten |
| `mnemlet_replace` | `memory_id, new_content, importance?` | `{old_id, new_id, old_status, new_memory}` | Ersetzen mit Verknüpfung |
| `mnemlet_confirm` | `memory_id` | `{memory_id, retention_score, boost_applied}` | Bestätigung, +0.20 |
| `mnemlet_context` | `query, namespace?, limit?, include_superseded?` | Context Pack Struktur | Intelligentes Recall |
| `mnemlet_explain` | `memory_id` | Provenance + Interactions + Policy | Erklärbarkeit |
| `mnemlet_classify` | `memory_id, memory_type?` | `{memory_id, memory_type, confidence}` | (Re-)Klassifizierung |

### Geänderte bestehende Endpunkte

**`mnemlet_ingest`** — erweiterte Rückgabe:
```json
{
    "memory_id": "...",
    "stored": true,
    "dedup": false,
    "namespace": "default",
    "retention_score": 0.25,
    "chunk_count": 1,
    "memory_type": "fact",           // NEU (NULL bis klassifiziert)
    "type_confidence": 0.91,         // NEU
    "contradiction_detected": false,  // NEU
    "superseded_ids": []              // NEU
}
```

**`mnemlet_recall`** — bleibt unverändert für Abwärtskompatibilität.

### Neue REST-Routen

| Route | Methode | Beschreibung |
|-------|---------|-------------|
| `/api/v1/context` | POST | Context Pack für Query |
| `/api/v1/explain/{memory_id}` | GET | Provenance für Memory |
| `/api/v1/classify/{memory_id}` | POST | (Re-)Klassifizierung |
| `/api/v1/remember` | POST | Explizite Speicherung |
| `/api/v1/forget/{memory_id}` | POST | Explizites Vergessen |
| `/api/v1/replace/{memory_id}` | POST | Ersetzen |

### Neue Konstanten (in `constants.py`)

```python
# Memory types
MEMORY_TYPES = ("fact", "preference", "instruction", "event", "context")

# Classification
CLASSIFICATION_LLM_MODEL = "gemma4-e2b:q4_0"
CLASSIFICATION_TIMEOUT_SECONDS = 30
CLASSIFICATION_RETRY_ATTEMPTS = 2

# Context Pack
PRIMARY_SCORE_THRESHOLD = 0.7
SUPPORTING_SCORE_THRESHOLD = 0.3
ABSTENTION_LOW_CONFIDENCE_THRESHOLD = 0.3
CONTRADICTION_AUTO_SUPERSEDE_THRESHOLD = 0.8

# Review Commands
BOOST_CONFIRM = 0.20

# Default Policies
DEFAULT_POLICIES = {
    "fact": {
        "min_retention_score": 0.10,
        "max_age_days": None,
        "supersede_on_contradiction": True,
        "require_confirmation_for_delete": False,
    },
    "preference": {
        "min_retention_score": 0.05,
        "max_age_days": None,
        "supersede_on_contradiction": True,
        "require_confirmation_for_delete": False,
    },
    "instruction": {
        "min_retention_score": 0.30,
        "max_age_days": None,
        "supersede_on_contradiction": False,
        "require_confirmation_for_delete": True,
    },
    "event": {
        "min_retention_score": 0.02,
        "max_age_days": 365,
        "supersede_on_contradiction": False,
        "require_confirmation_for_delete": False,
    },
    "context": {
        "min_retention_score": 0.02,
        "max_age_days": 90,
        "supersede_on_contradiction": True,
        "require_confirmation_for_delete": False,
    },
}

# New status
MEMORY_STATUS_FORGOTTEN = "forgotten"
```

---

## Risiken und Gegenmaßnahmen

| Risiko | Wahrscheinlichkeit | Auswirkung | Gegenmaßnahme |
|--------|-------------------|------------|---------------|
| **LLM nicht erreichbar bei Ingest** | Hoch (Pi-Umgebung) | Mittel | Fallback auf NULL-Typ + Nachklassifizierung im Sleep-Zyklus. Kein Blockieren des Ingest. |
| **Falsche Klassifikation** | Mittel | Niedrig | `type_confidence`-Score sichtbar. Agent kann via `mnemlet_classify` korrigieren. Heuristik-Fallback fängt Wildwest-Szenarien ab. |
| **False Positive Contradiction** | Mittel | Mittel | Nur bei LLM-Confidence >= 0.8 automatisch supersedet. Darunter nur Flaggung (`contradicts_with`). |
| **Performance-Overhead durch LLM-Calls** | Hoch | Mittel | Klassifikation und Contradiction-Check asynchron. Ingest returnt sofort, Intelligence reichert asynchron an. Sleep-Zyklus für Batch-Nachholung. |
| **Scope Creep in Policies** | Niedrig | Hoch | Strikte 5-Typen, keine Custom-Typen in v0.2. Policies konservativ, Defaults nicht-destruktiv. |
| **Migration bricht bestehende Daten** | Niedrig | Hoch | Alle neuen Spalten nullable. Migration ist reines `ADD COLUMN`. Kein Datenverlust möglich. Bestehende Queries funktionieren weiter. |
| **Abstention-Overtriggering** | Mittel | Niedrig | Schwellenwerte konservativ (0.3 für primary). Keine Abstention bei partial matches. Agent kann Context Pack nutzen, auch wenn abstention gesetzt ist. |
| **Superseded Memories clutter** | Niedrig | Niedrig | Purge-Decay berücksichtigt `superseded`-Status. Nach `max_age_days` werden supersedite Memories auf `cold_storage` verschoben. |

---

## Akzeptanzkriterien

1. **Klassifikation:** Jede neue Memory hat nach maximal einem Sleep-Zyklus einen `memory_type`. Wenn das LLM nicht erreichbar ist, ist `memory_type=NULL` und `type_source=NULL`. Der Heuristik-Fallback klassifiziert offensichtliche Fälle.

2. **Policies:** Ändert man `min_retention_score` für `instruction` auf 0.3, werden bestehende instructions mit `retention_score < 0.3` beim nächsten Decay-Zyklus nicht gelöscht sondern auf `cold_storage` geschoben.

3. **Context Pack:** `mnemlet_context` liefert bei Queries mit mindestens einem Score >= 0.3 ein Ergebnis in der `primary`- oder `supporting`-Gruppe. Bei komplett leeren Ergebnissen liefert es `abstention.reason = "no_relevant_memories"`.

4. **Supersession:** Wenn Memory A und B sich widersprechen und die Policy `supersede_on_contradiction=true` hat, wird A auf `status=superseded` gesetzt und B bekommt `supersedes=A.id` in metadata_json.

5. **Review Commands:** `mnemlet_remember` speichert immer (kein Dedup). `mnemlet_forget` setzt `status=forgotten`. `mnemlet_confirm` boostet retention_score um +0.20. `mnemlet_replace` verknüpft alte und neue Memory korrekt.

6. **Provenance:** `mnemlet_explain` liefert für jede Memory: source (vector/fts/hybrid), original_rank, decay_adjusted_score, type, age_days, access_count und policy_flags.

7. **Abwärtskompatibilität:** Bestehende `mnemlet_recall` und `mnemlet_ingest` funktionieren unverändert. Neue Felder in der Rückgabe sind additiv. `mnemlet_context` ist das neue empfohlene Recall-Tool, aber `mnemlet_recall` bleibt.

8. **Asynchronität:** Kein Ingest-Call blockiert länger als bisher wegen Intelligence-Operationen. Klassifikation und Contradiction-Check laufen asynchron oder im Sleep-Zyklus.

9. **Migration:** Alle `ALTER TABLE ADD COLUMN`-Statements laufen ohne Datenverlust. Bestehende Daten haben `memory_type=NULL`, was als "noch nicht klassifiziert" gilt.

---

## Tests die beweisen, dass es funktioniert

### Unit Tests

| Test | Beschreibt |
|------|-----------|
| `test_classifier_assigns_type` | LLM-Return → korrektes `memory_type` in DB |
| `test_classifier_fallback_on_llm_failure` | LLM nicht erreichbar → `type_source=null`, Memory trotzdem gespeichert |
| `test_classifier_all_five_types` | Alle 5 Typen werden korrekt erkannt |
| `test_classifier_heuristic_fallback` | Heuristik erkennt "bevorzugt" → preference, "immer" → instruction |
| `test_type_confidence_bounds` | `type_confidence` ist immer 0.0–1.0 |
| `test_policy_min_retention` | Policy verhindert Purge below threshold |
| `test_policy_supersede_flag` | `supersede_on_contradiction=false` → keine automatische Supersession |
| `test_policy_require_confirmation` | `require_confirmation_for_delete=true` → Memory nicht automatisch gelöscht |
| `test_context_pack_primary_supporting` | Scores >= 0.7 → primary, 0.3–0.7 → supporting, < 0.3 → nicht im Pack |
| `test_context_pack_superseded_grouping` | Superseded-Memories in eigener Gruppe |
| `test_context_pack_abstention_no_results` | Leere Ergebnisse → abstention reason "no_relevant_memories" |
| `test_context_pack_abstention_low_confidence` | Alle Scores < 0.3 → abstention mit Warnung |
| `test_context_pack_abstention_all_superseded` | Alle Ergebnisse supersedet → abstention mit Hinweis |
| `test_supersession_soft` | Alte Memory → status=superseded, neue → active |
| `test_supersession_preserves_old` | Superseded Memory bleibt in DB, nicht gelöscht |
| `test_supersession_links` | Neue Memory hat `supersedes=old_id`, alte hat `superseded_by=new_id` |
| `test_contradiction_detection_llm` | LLM erkennt Widerspruch korrekt (confidence > 0.8) |
| `test_contradiction_no_false_positive` | Verschiedene aber nicht-widersprüchliche Memories → kein Widerspruch |
| `test_contradiction_confidence_threshold` | LLM-confidence < 0.8 → nur Flaggung, keine Supersession |
| `test_provenance_fields` | Explain liefert alle geforderten Felder |
| `test_provenance_interactions` | Explain zeigt letzte Interaktionen |
| `test_remember_no_dedup` | `mnemlet_remember` speichert auch bei hohem Similarity-Score |
| `test_remember_explicit_type` | `mnemlet_remember` mit memory_type=instruction setzt den Typ direkt |
| `test_forget_status` | `mnemlet_forget` setzt status=forgotten |
| `test_forget_recoverable` | Vergessene Memory kann via mnemlet_update(status='active') reaktiviert werden |
| `test_forget_excluded_from_recall` | forgotten-Memories tauchen nicht im Recall auf |
| `test_replace_links` | Replace verknüpft alte und neue Memory korrekt |
| `test_replace_old_superseded` | Alte Memory hat status=superseded nach replace |
| `test_confirm_boost` | Confirm boostet retention_score um +0.20 |
| `test_confirm_interaction_recorded` | Confirm erzeugt interaction type='confirm' |
| `test_migration_add_columns` | ALTER TABLE läuft ohne Datenverlust |
| `test_migration_existing_data_null_type` | Bestehende Memories haben `memory_type=NULL` |

### Integration Tests

| Test | Beschreibt |
|------|-----------|
| `test_ingest_classify_contradiction_flow` | Kompletter Ingest → Klassifikation → Contradiction-Check → Supersession |
| `test_recall_to_context_pack` | Recall → Policy-Filter → Context Pack → Provenance |
| `test_context_pack_with_abstention` | Recall mit niedrigen Scores → Abstention |
| `test_review_commands_mcp` | Alle 4 Review-Commands via MCP-Endpunkt |
| `test_async_classification` | Ingest returnt sofort, Classification wird asynchron nachgereicht |
| `test_sleep_reclassifies_null_types` | Sleep-Zyklus klassifiziert Memories mit `memory_type=NULL` nach |
| `test_policy_override_per_namespace` | Namespace-spezifische Policy überschreibt Defaults |
| `test_decay_respects_policy_thresholds` | Decay berücksichtigt typ-spezifische min_retention_score |

### End-to-End Tests

| Test | Beschreibt |
|------|-----------|
| `test_full_lifecycle` | Remember → Confirm → Replace → Forget → Explain |
| `test_contradiction_supersede_lifecycle` | Ingest widersprüchliche Info → Auto-supersede → Recall zeigt nur aktuelle |
| `test_abstention_flow` | Query ohne Ergebnisse → Abstention → Remember → Query erfolgreich |
| `test_heuristic_fallback_lifecycle` | LLM nicht verfügbar → Heuristik-Klassifikation → LLM wieder da → Nachklassifizierung |
| `test_context_pack_full_structure` | Ingest 5 verschiedene Memories → Context Pack mit primary, supporting, abstention |

---

## Dateistruktur (vorgeschlagen)

```
src/mnemlet/
├── intelligence/              # NEU: Intelligence Layer
│   ├── __init__.py
│   ├── classifier.py          # Memory Classifier
│   ├── policy.py              # Policy Engine
│   ├── context_pack.py        # Context Pack Builder
│   ├── abstention.py          # No-Hit / Abstention Logic
│   ├── supersession.py        # Supersession / Contradiction Handler
│   ├── provenance.py          # Provenance / Explainability
│   └── review.py              # Review Commands (remember, forget, replace, confirm)
├── engine/                    # BESTEHEND, unverändert
│   ├── ingest.py
│   ├── recall.py
│   ├── decay.py
│   ├── sleep.py
│   └── llm.py                 # BESTEHEND, wird erweitert (Batch-Contradiction)
├── storage/                   # BESTEHEND, erweitert
│   ├── sqlite.py              # Migration + neue Spalten/Tabellen
│   ├── chroma.py
│   ├── vault.py
│   └── embeddings.py
├── server/
│   ├── mcp_server.py          # NEU: 7 neue MCP-Tools
│   ├── routes/
│   │   ├── context.py         # NEU
│   │   ├── explain.py         # NEU
│   │   ├── classify.py        # NEU
│   │   ├── remember.py        # NEU
│   │   ├── forget.py           # NEU
│   │   └── replace.py          # NEU
│   └── app.py                 # Erweitert: Intelligence Layer integrieren
├── constants.py               # NEU: Konstanten für Intelligence Layer
└── config.py                  # Erweitert: Intelligence-Konfiguration
```

---

## Offene Punkte (v0.2 nicht im Scope)

- **Benutzerdefinierte Typen:** v0.2 unterstützt nur die 5 festen Typen. Custom-Typen sind ein v0.3-Thema.
- **LLM-Modell-Config:** v0.2 nutzt das bestehende `llm.py`-Modell. Konfigurierbare Modelle kommen in v0.3.
- **Batch-Klassifikation:** Sleep-Zyklus klassifiziert NULL-Typen nach. Batch-Contradiction-Check ist v0.3.
- **Context Pack als Prompt-Generator:** v0.2 liefert nur strukturierte Ergebnisse. Prompt-Generation ist ein potenzielles v0.3-Feature.
- **Graph-basierte Provenance:** v0.2 nutzt `metadata_json`-Felder. Die bestehende `graph_edges`-Tabelle ist für v0.3+.