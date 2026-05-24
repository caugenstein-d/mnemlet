# Mnémlet Quality Benchmark Design

**Date:** 2026-05-22
**Status:** Draft
**Approach:** Separate Quality-Benchmark-Modell neben bestehendem Retrieval-Benchmark (Ansatz B)

## Problem

Der bestehende public-synthetic Benchmark mit 48 Queries misst Retrieval-Qualität (hit@K, precision, MRR, forbidden_hit_rate, etc.). Die Metriken zeigen: Top-3-Retrieval funktioniert (hit@3 = 1.0), aber Gedächtnisqualität hat deutliche Lücken (false_positive_rate 83%, forbidden_hit_rate 42%). Der bestehende Benchmark kann diese Lücken nicht differenzieren, weil sein Datenmodell auf Batch-Ingest → Query ausgelegt ist und keine sequenziellen Aktionen, Zeitsimulation oder Assertions jenseits von "ID in Top-K" unterstützt.

## Ziele

Ein Benchmark der echte Gedächtnisqualität misst, nicht nur Retrieval:

1. Dauerhafte Präferenzen erkennen (Wichtig/Flüchtiges unterscheiden)
2. Temporären Smalltalk ignorieren
3. Projektstand korrekt abrufen
4. Widersprüche erkennen (aspirational)
5. Alte Fakten durch neue ersetzen (aspirational)
6. Bei Unsicherheit nichts zurückgeben
7. Richtigen Kontext für Agenten bauen
8. Quellen/Provenance korrekt angeben
9. OpenCode- und OpenWebUI-Integration getrennt bewerten

## Entwurfsentscheidungen

### Ansatz B: Separates Quality-Benchmark-Modell

Neues `QualityScenario`-Modell mit `Phase`-Objekten neben dem bestehenden `BenchmarkCase`/`BenchmarkQuery`-Retrieval-Benchmark. Keine Breaking Changes am bestehenden System.

**Begründung:** Die 9 Qualitätskategorien brauchen fundamentally andere Teststrukturen (sequenzielle Aktionen, Zeitsimulation, Assertions wie `expect_empty`, `expect_score_above`). Diese in das bestehende `BenchmarkQuery`-Modell zu quetschen würde es überladen und die Abwärtskompatibilität gefährden.

### Aspirationale Kategorien

Kategorien 4 (contradiction_handling) und 5 (fact_evolution) sind als **aspirational** markiert. Sie laufen im aktuellen Zustand und dokumentieren das Verhalten "wie es ist". Failures dort sind erwartet. Wenn die Engine diese Fähigkeiten bekommt, werden aus Failures zu Passes. Aspirationale Kategorien gehen nicht in den Release-blocking Gesamtscore ein.

### Multi-Step mit Zeitsimulation

Jedes Szenario definiert eine Sequenz von Phasen mit Actions (ingest, update, advance_time, recall, boost). Zeit wird per `advance_time` simuliert (ändert `created_at` bzw. `last_accessed_at` der betroffenen Memories).

### Deterministisch + optionales LLM-Layer

Kern-Metriken sind voll deterministisch. Ein optionales LLM-Judge-Layer kann für qualitative Scores (Kohärenz, Widerspruchserkennung) dazugeschaltet werden, ist aber nie required für Pass/Fail.

---

## Benchmark-Kategorien

| # | Kategorie | Anforderung | Level | Was sie testet |
|---|-----------|-------------|-------|----------------|
| 1 | `preference_persistence` | Dauerhafte Präferenzen | current | Hochwichtige Erinnerungen überstehen Decay, während Low-Importance-Einträge verblassen |
| 2 | `ephemeral_rejection` | Temporären Smalltalk ignorieren | current | Smalltalk/Flüchtiges taucht nicht in relevanten Queries auf |
| 3 | `project_context` | Projektstand korrekt abrufen | current | Aus fuzzyen Kontexten wird das richtige Projekt-Detail geholt |
| 4 | `contradiction_handling` | Widersprüche erkennen | **aspirational** | Neuere/höher-Importance Fakt dominiert bei Widersprüchen |
| 5 | `fact_evolution` | Alte Fakten durch neue ersetzen | **aspirational** | Aktualisierter Fakt wird zurückgegeben, veralteter nicht |
| 6 | `uncertainty_gating` | Bei Unsicherheit nichts zurückgeben | current | Ambiguität, Low-Similarity, Cross-Namespace-Noise → leer statt falsch |
| 7 | `agent_context_assembly` | Richtigen Kontext für Agenten bauen | current | Injected Context ist relevant, vollständig, nicht überladen |
| 8 | `provenance_tracking` | Quellen/Provenance korrekt | current | Jedes Ergebnis trägt namespace, source, created_at korrekt |
| 9 | `opencode_integration_quality` | OpenCode-Integration | current | Plugin baut korrekten System-Prompt, ruft recall richtig |
| 10 | `openwebui_integration_quality` | OpenWebUI-Integration | current | Filter inlet/outlet funktionieren korrekt mit echtem Memory-Content |

---

## Dataset-Struktur

### Neues Datenmodell: QualityScenario

```json
{
  "name": "quality-synthetic",
  "version": 1,
  "type": "quality",
  "scenarios": [
    {
      "id": "preference_persistence_editor_vs_trivia",
      "category": "preference_persistence",
      "description": "High-importance preference survives 60 days of decay while trivia fades",
      "aspirational": false,
      "phases": [
        {
          "step": 1,
          "action": "ingest",
          "memories": [
            {
              "id": "pref_dark_theme",
              "content": "Christoph prefers dark editor themes for long coding sessions.",
              "namespace": "preferences",
              "importance": 0.9,
              "tags": ["editor", "preference"]
            }
          ]
        },
        {
          "step": 2,
          "action": "advance_time",
          "days": 60
        },
        {
          "step": 3,
          "action": "recall",
          "query": "What editor theme does Christoph prefer?",
          "namespace": "preferences",
          "assertions": {
            "expect_in_top": ["pref_dark_theme"],
            "expect_not_in_results": ["trivia_rainy_tuesday"],
            "expect_score_above": {"pref_dark_theme": 0.3}
          }
        }
      ]
    }
  ]
}
```

### Phase-Actions

| Action | Felder | Beschreibung |
|--------|--------|--------------|
| `ingest` | `memories[]` | Speichert Memories mit id, content, namespace, importance, tags, status |
| `update` | `memory_id`, `content`, `importance` | Aktualisiert eine bestehende Memory. `memory_id` bezieht sich auf die scenario-interne logische ID, der Runner mappt auf die interne UUID. |
| `advance_time` | `days` | Simuliert Zeitverlauf für Decay-Berechnung |
| `recall` | `query`, `namespace`, `assertions` | Führt Recall-Query aus und prüft Assertions |
| `boost` | `memory_id`, `interaction_type` | Wendet Boost auf eine Memory an. `memory_id` bezieht sich auf die scenario-interne logische ID. |
| `check_adapter` | `surface`, `check`, `assertions` | Prüft Integration-Adapter-Verhalten (inlet/outlet) |
| `check_adapter` | `surface`, `check`, `assertions` | Prüft Integration-Adapter-Verhalten |

### Assertion-Typen

| Assertion | Typ | Beschreibung |
|-----------|-----|--------------|
| `expect_in_top` | `list[str]` | Memory-IDs müssen in Top-K Ergebnissen sein |
| `expect_not_in_results` | `list[str]` | Memory-IDs dürfen nicht in Ergebnissen sein |
| `expect_rank_range` | `dict[str, [min, max]]` | Memory muss an Position min..max stehen |
| `expect_score_above` | `dict[str, float]` | Score der Memory muss über Schwelle sein |
| `expect_score_below` | `dict[str, float]` | Score der Memory muss unter Schwelle sein |
| `expect_empty` | `bool` | Ergebnisliste muss leer sein |
| `expect_substring` | `list[str]` | Mindestens ein Ergebnis muss Substring enthalten |
| `expect_namespace` | `list[str]` | Alle Ergebnisse müssen aus diesen Namespaces stammen |
| `expect_provenance_field` | `list[str]` | Jedes Ergebnis muss diese Felder haben |
| `expect_result_count_range` | `[min, max]` | Anzahl Ergebnisse muss in Range sein |
| `expect_contradiction_flag` | `bool` | Aspirational: System sollte Widerspruchs-Flag setzen |
| `expect_contains` | `list[str]` | Adapter-Output muss diese Strings enthalten |
| `expect_adapter_calls_endpoint` | `str` | Adapter muss diesen API-Endpunkt aufgerufen haben |

### Dateistruktur

```
benchmarks/
  public/
    synthetic_memory_cases.json        # bestehend, 48 Queries (Retrieval)
    synthetic_quality_scenarios.json    # NEU: Quality-Benchmark
  private/
    .gitkeep
    real_world_cases.json               # bestehend (leer)
    real_quality_scenarios.json         # NEU: Private Quality-Scenarios
```

Public-Datasets sind synthetisch und commit-safe. Private-Datasets dürfen echte Daten enthalten und werden von `.gitignore` ausgeschlossen.

Das `version`-Feld erlaubt Schema-Evolution ohne Breaking Changes.

---

## Metriken

### Schicht 1: Deterministische Kernmetriken (Pflicht, kein LLM)

| Metrik | Formel/Beschreibung | Kategorien |
|--------|---------------------|------------|
| `scenario_pass_rate` | Anteil Szenarien mit 0 Assertion-Failures | alle |
| `assertion_pass_rate` | Anteil erfolgreicher Assertions über alle Szenarien | alle |
| `top_k_accuracy` | Erwartete Memory in Top-K (K=1,3,5) | preference, project_context, contradiction, fact_evolution |
| `rejection_rate` | Anteil korrekt abgelehnter Memories (expect_not_in_results) | ephemeral_rejection, uncertainty_gating |
| `false_positive_rate` | Anteil Queries die irrtümlich Ergebnisse liefern | uncertainty_gating |
| `score_discrimination` | Differenz erwarteter Score minus höchster Distraktor-Score | preference_persistence |
| `rank_accuracy` | Erwartete Memory an korrekter Position (expect_rank_range) | project_context, preference_persistence |
| `empty_correct_rate` | Wie oft liefert no-hit-Szenario korrekt leere Liste | uncertainty_gating |
| `provenance_completeness` | Anteil Ergebnisse mit allen provenance_fields | provenance_tracking |
| `result_count_accuracy` | Anteil Queries wo Ergebnisanzahl in expect_result_count_range liegt | agent_context_assembly |

### Schicht 2: Kategorie-spezifische Metriken (Pflicht, kein LLM)

| Metrik | Beschreibung | Kategorie |
|--------|-------------|-----------|
| `preference_decay_ratio` | Score(high_importance) / Score(low_importance) nach Zeit → > 1.0 | preference_persistence |
| `ephemeral_suppression_ratio` | Anteil Queries wo Smalltalk nicht in Top-5 | ephemeral_rejection |
| `contradiction_resolution_rate` | Anteil Szenarien wo neuere/höhere Memory dominiert | contradiction_handling (aspirational) |
| `fact_evolution_accuracy` | Anteil Queries mit aktualisiertem Fakt statt veraltetem | fact_evolution (aspirational) |
| `uncertainty_precision` | TP/(TP+FP) bei "nichts zurückgeben" | uncertainty_gating |
| `context_relevance_ratio` | Anteil injizierter Kontext-Elemente die zur Query passen | agent_context_assembly |
| `context_bloat_ratio` | Ergebnis-Tokens / Max-Budget → < 1.0 | agent_context_assembly |
| `integration_inlet_success_rate` | Anteil korrekter System-Prompt-Injections | opencode_integration, openwebui_integration |
| `integration_outlet_success_rate` | Anteil korrekter Ingest-Aufrufe | openwebui_integration |

### Schicht 3: Optionales LLM-Layer (nicht für Pass/Fail)

| Metrik | Beschreibung | Kategorien |
|--------|-------------|------------|
| `context_coherence_score` | LLM bewertet Kohärenz und Relevanz des injizierten Kontexts | agent_context_assembly |
| `contradiction_detection_score` | LLM bewertet Widerspruchserkennung | contradiction_handling |
| `evolution_clarity_score` | LLM bewertet Klarheit der Antwort zum aktuellen Fakt | fact_evolution |

LLM-Scores werden als `llm_assisted: true` markiert und gehen nicht in Pass/Fail ein.

### Aggregation

```
Quality-Gesamtscore =
  (scenario_pass_rate × 0.30)
+ (assertion_pass_rate × 0.30)
+ (top_k_accuracy@3 × 0.20)
+ (rejection_rate × 0.10)
+ (score_discrimination_normalized × 0.10)
```

Aspirationale Kategorien werden separat ausgewiesen und gehen **nicht** in den Gesamtscore ein.

---

## Failure Cases

| Kategorie | Failure Label | Beschreibung | Aktuell erwartbar? |
|-----------|---------------|--------------|---------------------|
| `preference_persistence` | `preference_lost` | Erwartete Preference fehlt in Top-K | Ja |
| `preference_persistence` | `preference_below_trivia` | Hochwichtige Preference rankt unter Low-Importance-Trivia | Ja |
| `preference_persistence` | `preference_decayed_below_threshold` | Preference-Score fällt nach Zeitsimulation unter Schwelle | Ja |
| `ephemeral_rejection` | `ephemeral_in_results` | Smalltalk taucht in Ergebnissen auf | Ja |
| `ephemeral_rejection` | `ephemeral_ranked_above_relevant` | Smalltalk rankt höher als relevante Memory | Ja |
| `project_context` | `wrong_project_detail` | Falsches Projekt-Detail wird zurückgegeben | Ja |
| `project_context` | `context_overflow` | Zu viele irrelevante Ergebnisse verdecken das gesuchte | Ja |
| `contradiction_handling` | `contradiction_unresolved` | Beide widersprüchlichen Fakten kommen zurück | Ja (aspirational) |
| `contradiction_handling` | `stale_fact_dominates` | Veralteter Fakt rankt höher als neuer | Ja (aspirational) |
| `fact_evolution` | `obsolete_fact_returned` | Veralteter Wert statt aktualisiertem | Ja (aspirational) |
| `fact_evolution` | `duplicate_facts` | Alter und neuer Fakt beide in Ergebnissen | Ja (aspirational) |
| `uncertainty_gating` | `false_positive` | System gibt Ergebnisse zurück bei no-hit | Ja (83%) |
| `uncertainty_gating` | `low_confidence_noise` | Ergebnisse mit Score < 0.2 kommen durch | Ja |
| `uncertainty_gating` | `cross_namespace_leak` | Ergebnisse aus falschem Namespace | Ja |
| `agent_context_assembly` | `missing_key_context` | Kritische Memory fehlt im injizierten Kontext | Ja |
| `agent_context_assembly` | `bloat_over_budget` | Injizierter Kontext überschreitet Token-Budget | Ja |
| `provenance_tracking` | `missing_namespace` | Ergebnis hat kein namespace-Feld | Nein |
| `provenance_tracking` | `missing_source` | Ergebnis hat kein source-Feld | Nein |
| `provenance_tracking` | `wrong_namespace` | Ergebnis hat falsches namespace | Nein |
| `opencode_integration` | `inlet_missing_context` | System-Prompt enthält keinen Mnémlet-Kontext | Nein |
| `opencode_integration` | `inlet_wrong_format` | Kontext hat falsches Format im System-Prompt | Nein |
| `openwebui_integration` | `outlet_missing_ingest` | Assistant-Antwort wird nicht an ingest weitergegeben | Nein |
| `openwebui_integration` | `inlet_injection_failure` | Filter injectet keinen Kontext | Nein |

---

## Mindest-Schwellen für Release-Ready

### Tier 1: Must-Pass (Blocker)

| Metrik | Schwelle | Begründung |
|--------|----------|------------|
| `scenario_pass_rate` (current) | ≥ 0.80 | 80% der Szenarien müssen vollständig bestehen |
| `top_k_accuracy@3` | ≥ 0.90 | Richtige Memory in Top-3 – aktuell 1.0, darf nicht regressieren |
| `empty_correct_rate` | ≥ 0.67 | Mindestens 2/3 der no-hit-Szenarien müssen leer bleiben |
| `forbidden_hit_rate` | ≤ 0.25 | Maximal jeder vierte Query darf verbotene Memory zurückgeben |
| `false_positive_rate` (no_hit) | ≤ 0.33 | Maximal jeder dritte no-hit-Query darf Ergebnisse liefern |
| `provenance_completeness` | ≥ 0.95 | Nahezu jedes Ergebnis muss alle Provenance-Felder haben |
| `integration_inlet_success_rate` | = 1.0 | Integration-Tests müssen zu 100% passen |

### Tier 2: Should-Pass (empfohlen, nicht-blocking)

| Metrik | Schwelle | Begründung |
|--------|----------|------------|
| `assertion_pass_rate` | ≥ 0.85 | Mehr als 4 von 5 Assertions müssen bestehen |
| `score_discrimination` | ≥ 0.15 | Erwartete Memory mind. 0.15 Score über stärkstem Distraktor |
| `preference_decay_ratio` | ≥ 1.5 | Hochwichtig muss nach Decay mind. 1.5x den Score von Low-Importance haben |
| `context_bloat_ratio` | ≤ 0.9 | Injizierter Kontext darf Token-Budget zu ≤ 90% ausnutzen |
| `rank_accuracy` | ≥ 0.80 | Erwartete Memory an korrekter Position |

### Tier 3: Aspirational (Dokumentation, nicht-blocking)

| Metrik | Schwelle | Status |
|--------|----------|--------|
| `contradiction_resolution_rate` | ≥ 0.60 | Noch nicht implementiert |
| `fact_evolution_accuracy` | ≥ 0.60 | Noch nicht implementiert |
| `llm_assisted` scores | Dokumentativ | Nur mit `--with-llm-judge` Flag |

### Regressions-Checks

| Check | Regel |
|-------|-------|
| `top_k_accuracy@3` | Darf nicht um > 0.05 fallen |
| `scenario_pass_rate` | Darf nicht um > 0.10 fallen |
| `any_tier1_metric` | Darf nicht von "pass" auf "fail" wechseln |

---

## Report-Struktur

### Output-Formate

JSON (maschinenlesbar), Markdown (menschenlesbar), CSV (Tabellen-Export). Zeitreihen-Vergleich per `--compare-to`.

### Dateistruktur

```
benchmark-results/
  latest/
    quality/
      report.md
      results.json
      scenarios.csv
  history/
    2026-05-22T12-00-00Z/
      quality/
        report.md
        results.json
        scenarios.csv
```

### JSON-Struktur

```json
{
  "run_id": "2026-05-22T12-00-00Z",
  "mode": "quality",
  "dataset": "quality-synthetic",
  "dataset_version": 1,
  "command": "mnemlet benchmark quality --dataset public --output ...",
  "environment": { ... },
  "summary": {
    "total_scenarios": 42,
    "passed_scenarios": 31,
    "failed_scenarios": 11,
    "scenario_pass_rate": 0.738,
    "total_assertions": 156,
    "passed_assertions": 129,
    "failed_assertions": 27,
    "assertion_pass_rate": 0.827,
    "top_k_accuracy_at_1": 0.76,
    "top_k_accuracy_at_3": 0.88,
    "top_k_accuracy_at_5": 0.92,
    "rejection_rate": 0.45,
    "false_positive_rate": 0.55,
    "empty_correct_rate": 0.33,
    "score_discrimination_mean": 0.12,
    "preference_decay_ratio": 1.8,
    "ephemeral_suppression_ratio": 0.55,
    "provenance_completeness": 1.0,
    "context_bloat_ratio": 0.65,
    "p50_latency_ms": 15.2,
    "p95_latency_ms": 22.4,
    "max_latency_ms": 28.1
  },
  "tier_results": {
    "tier1_blockers": {
      "scenario_pass_rate": {"value": 0.738, "threshold": 0.80, "pass": false},
      "top_k_accuracy_at_3": {"value": 0.88, "threshold": 0.90, "pass": false},
      "empty_correct_rate": {"value": 0.33, "threshold": 0.67, "pass": false},
      "forbidden_hit_rate": {"value": 0.25, "threshold": 0.25, "pass": true},
      "false_positive_rate": {"value": 0.55, "threshold": 0.33, "pass": false},
      "provenance_completeness": {"value": 1.0, "threshold": 0.95, "pass": true},
      "integration_inlet_success_rate": {"value": 1.0, "threshold": 1.0, "pass": true}
    },
    "tier2_recommended": { ... },
    "tier3_aspirational": { ... }
  },
  "regression": {
    "has_regression": true,
    "regressions": [
      {
        "metric": "scenario_pass_rate",
        "previous": 0.85,
        "current": 0.738,
        "delta": -0.112,
        "threshold": "must_not_fall_by_0.10"
      }
    ]
  },
  "category_summary": {
    "preference_persistence": {"scenarios": 5, "passed": 4, "assertion_pass_rate": 0.87},
    "ephemeral_rejection": {"scenarios": 4, "passed": 1, "assertion_pass_rate": 0.35},
    "contradiction_handling": {"scenarios": 4, "passed": 0, "assertion_pass_rate": 0.0, "aspirational": true},
    "fact_evolution": {"scenarios": 4, "passed": 0, "assertion_pass_rate": 0.0, "aspirational": true},
    "uncertainty_gating": {"scenarios": 5, "passed": 2, "assertion_pass_rate": 0.50},
    "agent_context_assembly": {"scenarios": 4, "passed": 3, "assertion_pass_rate": 0.78},
    "provenance_tracking": {"scenarios": 4, "passed": 4, "assertion_pass_rate": 1.0},
    "opencode_integration_quality": {"scenarios": 4, "passed": 4, "assertion_pass_rate": 1.0},
    "openwebui_integration_quality": {"scenarios": 4, "passed": 4, "assertion_pass_rate": 1.0}
  },
  "scenarios": [ ... ],
  "llm_assisted": null
}
```

### CSV-Struktur (scenarios.csv)

```csv
scenario_id,category,phase_step,action,assertion_type,expected,actual,pass,failure_label,duration_ms
preference_persistence_editor_vs_trivia,preference_persistence,3,recall,expect_in_top,"[""pref_editor_dark""]","[""pref_editor_dark"", ""trivia_weather""]",true,,12.4
preference_persistence_editor_vs_trivia,preference_persistence,3,recall,expect_not_in_results,"[""trivia_weather""]","[""trivia_weather""]",false,ephemeral_in_results,12.4
```

### Regression-Vergleich

Mit `--compare-to <path>` wird eine `regression.json` erzeugt:

```json
{
  "baseline_run_id": "2026-05-20T08-00-00Z",
  "current_run_id": "2026-05-22T12-00-00Z",
  "regressions": [...],
  "improvements": [...],
  "unchanged": [...]
}
```

---

## Dataset-Beispiele

### 1. preference_persistence

```json
{
  "id": "preference_persistence_editor_vs_trivia",
  "category": "preference_persistence",
  "description": "High-importance editor preference survives 60 days of decay while low-importance trivia fades below recall threshold",
  "aspirational": false,
  "phases": [
    {
      "step": 1, "action": "ingest",
      "memories": [
        {"id": "pref_dark_theme", "content": "Christoph prefers dark editor themes for long coding sessions.", "namespace": "preferences", "importance": 0.9, "tags": ["editor", "preference"]},
        {"id": "trivia_rainy_tuesday", "content": "It was rainy last Tuesday.", "namespace": "preferences", "importance": 0.1, "tags": ["weather", "smalltalk"]}
      ]
    },
    {"step": 2, "action": "advance_time", "days": 60},
    {
      "step": 3, "action": "recall",
      "query": "What editor theme does Christoph prefer for coding?",
      "namespace": "preferences",
      "assertions": {
        "expect_in_top": ["pref_dark_theme"],
        "expect_not_in_results": ["trivia_rainy_tuesday"],
        "expect_score_above": {"pref_dark_theme": 0.3}
      }
    }
  ]
}
```

### 2. ephemeral_rejection

```json
{
  "id": "ephemeral_smalltalk_absent",
  "category": "ephemeral_rejection",
  "description": "Smalltalk about lunch and weather should not appear when querying for architectural decisions",
  "aspirational": false,
  "phases": [
    {
      "step": 1, "action": "ingest",
      "memories": [
        {"id": "arch_decision_mnemlet", "content": "The memory engine uses a hybrid search combining vector similarity and FTS5.", "namespace": "project", "importance": 0.85, "tags": ["architecture", "decision"]},
        {"id": "lunch_burrito", "content": "We had burritos for lunch yesterday.", "namespace": "project", "importance": 0.15, "tags": ["smalltalk", "food"]},
        {"id": "weather_sunny", "content": "It was sunny on Saturday morning.", "namespace": "project", "importance": 0.1, "tags": ["smalltalk", "weather"]}
      ]
    },
    {
      "step": 2, "action": "recall",
      "query": "How does the search architecture work?",
      "namespace": "project",
      "assertions": {
        "expect_in_top": ["arch_decision_mnemlet"],
        "expect_not_in_results": ["lunch_burrito", "weather_sunny"],
        "expect_result_count_range": [1, 3]
      }
    }
  ]
}
```

### 3. project_context

```json
{
  "id": "project_context_correct_stack_detail",
  "category": "project_context",
  "description": "Query about the database layer should return SQLite info, not the web framework info",
  "aspirational": false,
  "phases": [
    {
      "step": 1, "action": "ingest",
      "memories": [
        {"id": "stack_fastapi", "content": "The memory service exposes HTTP routes through FastAPI.", "namespace": "project-stack", "importance": 0.7},
        {"id": "stack_sqlite", "content": "SQLite stores durable memory metadata for Mnémlet.", "namespace": "project-stack", "importance": 0.8},
        {"id": "stack_chroma", "content": "ChromaDB backs vector similarity search in the local memory engine.", "namespace": "project-stack", "importance": 0.8}
      ]
    },
    {
      "step": 2, "action": "recall",
      "query": "Which database stores the durable metadata?",
      "namespace": "project-stack",
      "assertions": {
        "expect_in_top": ["stack_sqlite"],
        "expect_rank_range": {"stack_sqlite": [1, 2]}
      }
    }
  ]
}
```

### 4. contradiction_handling (aspirational)

```json
{
  "id": "contradiction_port_change",
  "category": "contradiction_handling",
  "description": "When two memories contradict about a port number, the newer/higher-importance one should dominate",
  "aspirational": true,
  "phases": [
    {
      "step": 1, "action": "ingest",
      "memories": [
        {"id": "port_old_8080", "content": "The service runs on port 8080.", "namespace": "infra", "importance": 0.5}
      ]
    },
    {
      "step": 2, "action": "ingest",
      "memories": [
        {"id": "port_new_9090", "content": "The service now runs on port 9090 after the migration.", "namespace": "infra", "importance": 0.8}
      ]
    },
    {
      "step": 3, "action": "recall",
      "query": "What port does the service run on?",
      "namespace": "infra",
      "assertions": {
        "expect_in_top": ["port_new_9090"],
        "expect_not_in_results": ["port_old_8080"],
        "expect_contradiction_flag": true
      }
    }
  ]
}
```

### 5. fact_evolution (aspirational)

```json
{
  "id": "fact_evolution_api_version",
  "category": "fact_evolution",
  "description": "An updated API version memory should replace the outdated one in recall results",
  "aspirational": true,
  "phases": [
    {
      "step": 1, "action": "ingest",
      "memories": [
        {"id": "api_v1", "content": "The Mnémlet API is at version 1.", "namespace": "project", "importance": 0.6}
      ]
    },
    {
      "step": 2, "action": "update",
      "memory_id": "api_v1",
      "content": "The Mnémlet API is at version 2, migrating from v1.",
      "importance": 0.7
    },
    {
      "step": 3, "action": "recall",
      "query": "What version is the Mnémlet API?",
      "namespace": "project",
      "assertions": {
        "expect_in_top": ["api_v1"],
        "expect_substring": ["version 2"]
      }
    }
  ]
}
```

### 6. uncertainty_gating

```json
{
  "id": "uncertainty_no_relevant_memory",
  "category": "uncertainty_gating",
  "description": "A query about topic X in namespace Y should return nothing when namespace Y contains only unrelated memories",
  "aspirational": false,
  "phases": [
    {
      "step": 1, "action": "ingest",
      "memories": [
        {"id": "kitchen_recipe", "content": "A good pancake recipe uses flour, eggs, and milk.", "namespace": "devops", "importance": 0.4},
        {"id": "kitchen_garden", "content": "Tomatoes grow well in raised beds with southern exposure.", "namespace": "devops", "importance": 0.4}
      ]
    },
    {
      "step": 2, "action": "recall",
      "query": "What is the CI/CD deployment pipeline configuration?",
      "namespace": "devops",
      "assertions": {
        "expect_empty": true,
        "expect_not_in_results": ["kitchen_recipe", "kitchen_garden"]
      }
    }
  ]
}
```

### 7. agent_context_assembly

```json
{
  "id": "agent_context_relevant_within_budget",
  "category": "agent_context_assembly",
  "description": "Recall for an agent query should return relevant memories within token budget, not overflow with noise",
  "aspirational": false,
  "phases": [
    {
      "step": 1, "action": "ingest",
      "memories": [
        {"id": "ctx_pref_shell", "content": "Christoph prefers concise shell commands with quoted paths.", "namespace": "agent-prefs", "importance": 0.8},
        {"id": "ctx_pref_status", "content": "Christoph wants status updates only when they add meaningful information.", "namespace": "agent-prefs", "importance": 0.7},
        {"id": "ctx_pref_dark", "content": "Christoph prefers dark editor themes for long coding sessions.", "namespace": "agent-prefs", "importance": 0.9},
        {"id": "ctx_trivia_lunch", "content": "We had sandwiches for lunch.", "namespace": "agent-prefs", "importance": 0.1}
      ]
    },
    {
      "step": 2, "action": "recall",
      "query": "What are Christoph's preferences for coding and communication?",
      "namespace": "agent-prefs",
      "assertions": {
        "expect_in_top": ["ctx_pref_dark", "ctx_pref_shell", "ctx_pref_status"],
        "expect_not_in_results": ["ctx_trivia_lunch"],
        "expect_result_count_range": [3, 5],
        "expect_provenance_field": ["namespace", "source"]
      }
    }
  ]
}
```

### 8. provenance_tracking

```json
{
  "id": "provenance_all_fields_present",
  "category": "provenance_tracking",
  "description": "Every recalled memory must carry namespace, source, and created_at",
  "aspirational": false,
  "phases": [
    {
      "step": 1, "action": "ingest",
      "memories": [
        {"id": "prov_stack_db", "content": "SQLite stores durable memory metadata.", "namespace": "provenance-test", "importance": 0.8}
      ]
    },
    {
      "step": 2, "action": "recall",
      "query": "What stores durable metadata?",
      "namespace": "provenance-test",
      "assertions": {
        "expect_in_top": ["prov_stack_db"],
        "expect_provenance_field": ["namespace", "source", "created_at"]
      }
    }
  ]
}
```

### 9. opencode_integration_quality

```json
{
  "id": "opencode_context_injection",
  "category": "opencode_integration_quality",
  "description": "The OpenCode plugin must inject Mnémlet context into the system prompt within token limits",
  "aspirational": false,
  "phases": [
    {
      "step": 1, "action": "ingest",
      "memories": [
        {"id": "oc_sentinel", "content": "Christoph calls the Mnémlet OpenCode bridge Nebelkrähe.", "namespace": "integration/sentinel", "importance": 0.95}
      ]
    },
    {
      "step": 2, "action": "recall",
      "query": "What is the Mnémlet OpenCode bridge called?",
      "namespace": "integration/sentinel",
      "assertions": {
        "expect_in_top": ["oc_sentinel"],
        "expect_substring": ["Nebelkrähe"],
        "expect_result_count_range": [1, 3],
        "expect_provenance_field": ["namespace", "source"]
      }
    },
    {
      "step": 3, "action": "check_adapter",
      "surface": "opencode",
      "check": "inlet_injects_recall_context",
      "assertions": {
        "expect_contains": ["Relevant context from Mnémlet memory", "Nebelkrähe"]
      }
    }
  ]
}
```

### 10. openwebui_integration_quality

```json
{
  "id": "openwebui_inlet_outlet",
  "category": "openwebui_integration_quality",
  "description": "The OpenWebUI filter must inject context at inlet and ingest assistant responses at outlet",
  "aspirational": false,
  "phases": [
    {
      "step": 1, "action": "ingest",
      "memories": [
        {"id": "owui_sentinel", "content": "Christoph calls the Mnémlet OpenCode bridge Nebelkrähe.", "namespace": "integration/sentinel", "importance": 0.95}
      ]
    },
    {
      "step": 2, "action": "recall",
      "query": "What is the bridge codename?",
      "namespace": "integration/sentinel",
      "assertions": {
        "expect_in_top": ["owui_sentinel"],
        "expect_substring": ["Nebelkrähe"]
      }
    },
    {
      "step": 3, "action": "check_adapter",
      "surface": "openwebui",
      "check": "inlet_injects_context",
      "assertions": {
        "expect_contains": ["Relevant context", "Nebelkrähe"]
      }
    },
    {
      "step": 4, "action": "check_adapter",
      "surface": "openwebui",
      "check": "outlet_ingests_response",
      "assertions": {
        "expect_adapter_calls_endpoint": "/api/v1/ingest"
      }
    }
  ]
}
```

---

## Akzeptanzkriterien

### Für den Benchmark selbst

| Kriterium | Bedingung |
|-----------|-----------|
| Schema-Validierung | Jedes Szenario muss gegen das JSON-Schema validieren. Ungültige Szenarien → harter Fehler. |
| Abwärtskompatibilität | Das bestehende Retrieval-Benchmark bleibt unverändert. Keine Breaking Changes. |
| Isolation | Jeder Szenario-Lauf bekommt isolierten Storage (`tempfile.mkdtemp`). Kein Shared State. |
| Commit-Safety | Public-Dataset enthält nur synthetische, nicht-personalisierte Daten. Keine echten Namen, IPs, Hostnamen. |
| Private-Isolation | `benchmarks/private/` wird von `.gitignore` ausgeschlossen. Private Szenarien dürfen nie automatisch committed werden. |
| LLM-Optionalität | Ohne `--with-llm-judge` läuft der Benchmark vollständig deterministisch. LLM-Ergebnisse gehen nicht in Pass/Fail. |
| Versionierung | `dataset_version` im Dataset und Report. Runner lehnt Szenarien mit unbekannter Version ab. |
| Report-Vollständigkeit | Jeder Lauf produziert JSON + MD + CSV. Fehlende Formate → Fehler. |
| Regression-Detect | `--compare-to` Flag vergleicht gegen vorherigen Lauf. Tier-1-Regressions-Check ist Pflicht. |
| Aspirational-Trennung | Aspirationale Kategorien werden separat ausgewiesen. Failures gehen nicht in Release-blocking Scores ein. |
| Laufzeit | Ein Quality-Benchmark-Durchlauf (public, ohne LLM-Judge) muss in unter 120 Sekunden auf einem Pi 5 abschließen. |

### Für die Engine (Release-Blocking)

| Kriterium | Bedingung |
|-----------|-----------|
| Alle Tier-1-Metriken bestehen | Jede Tier-1-Metrik ≥ Threshold |
| Keine Tier-1-Regressions | Keine Metrik fällt um mehr als die definierte Delta-Regel |
| Retrieval-Benchmark unverändert | Der bestehende 48-Query-Run produziert gleiche oder bessere Ergebnisse |

### Für "Quality-Benchmark ist bereit zur Implementierung"

| Kriterium | Bedingung |
|-----------|-----------|
| Design-Doc reviewed | Dieses Dokument wurde von Christoph approved |
| Public-Dataset hat ≥ 30 Szenarien | 10 Kategorien × 3+ Szenarien pro Kategorie |
| Runner-Code existiert und ist getestet | `QualityRunner`, `QualityScenario`, `Phase`, Schema-Validierung |
| Report-Generierung funktioniert | JSON, MD, CSV für einen Testlauf erzeugt |
| CI-Integration | `mnemlet benchmark quality` läuft in CI ohne LLM-Judge |