# Mnémlet Benchmark Reporting Design

Date: 2026-05-21
Status: Approved design, pending implementation plan

## Goal

Build a reproducible benchmark and reporting system for Mnémlet so the project can be published with defensible quality claims instead of anecdotal self-tests.

The work has two connected goals:

1. Fix the Sleep Engine's repeated empty consolidation loop so Mnémlet behaves cleanly during long idle periods.
2. Add benchmark infrastructure that measures retrieval quality, integration quality, and latency across Mnémlet core, REST, MCP, OpenWebUI, and OpenCode.

The public GitHub-facing benchmark must be reproducible and free of Christoph's private data. A separate private real-world benchmark may use local data but must never be committed.

## Current Evidence

### Runtime state observed before this design

- Mnémlet runs as a user service on `http://127.0.0.1:4050`.
- OpenWebUI runs as a user service on `127.0.0.1:8080`.
- OpenCode MCP reports `mnemlet connected`.
- Mnémlet REST `/api/v1/status` and MCP `/mcp/` initialize respond with HTTP 200.
- Live recall of the integration sentinel returns the expected codename `Nebelkrähe`.
- Mnémlet had no observed 4xx/5xx/errors in the inspected service logs.

### Sleep Engine issue

The Sleep Engine currently logs repeated pairs of:

```text
[sleep] Inactivity threshold reached, starting consolidation...
[sleep] Consolidation complete
```

Root cause: after a consolidation run completes, `_last_activity` remains older than the inactivity threshold and `_running` becomes false. `should_sleep()` therefore becomes true again on the next monitor check, even if nothing new happened. Existing checkpoints also persist across runs, so the repeated runs are mostly empty.

This is not a data-loss bug, but it is noisy and unpolished. It should be fixed before a public release.

## Design Principles

- Use test-driven development for each bugfix and new benchmark component.
- Keep public benchmark data synthetic and commit-safe.
- Keep private real-world benchmark data local and ignored by git.
- Separate retrieval quality from integration quality.
- Separate stable adapter-level tests from fragile live end-to-end tests.
- Generate machine-readable and human-readable reports.
- Only make GitHub claims that are directly supported by benchmark output.
- Add explicit pause gates during implementation so long work does not run unattended into usage limits.

## Architecture

### Sleep Engine lifecycle

The Sleep Engine should behave as a real cycle:

```text
active use -> idle threshold reached -> consolidation run -> completed/cooldown -> wait for new activity or next allowed window
```

Required behavior:

- After a successful consolidation run, `should_sleep()` must not immediately return true again.
- Checkpoints must be scoped to a single consolidation run, or otherwise reset in a controlled way before the next valid run.
- A new activity bump should allow a future sleep cycle after the inactivity threshold is reached again.
- Parallel runs must remain prevented.
- Status should expose enough information to understand the sleep state.

Candidate states:

- `idle`
- `running`
- `completed`
- `paused`

The implementation may use a `last_completed_at` timestamp, update `_last_activity` after completion, or introduce an explicit cooldown. The chosen implementation must be covered by tests and must avoid arbitrary sleeps in the test suite.

### Benchmark package

Add a benchmark package under:

```text
src/mnemlet/benchmark/
  __init__.py
  datasets.py
  runner.py
  metrics.py
  reports.py
  adapters.py
  live.py
```

Responsibilities:

- `datasets.py`: load and validate public/private benchmark datasets.
- `runner.py`: create isolated benchmark stores, ingest corpus memories, execute benchmark queries, collect raw results.
- `metrics.py`: compute retrieval and integration metrics.
- `reports.py`: write JSON, Markdown, and CSV reports.
- `adapters.py`: run stable adapter-level checks for OpenWebUI and OpenCode integration surfaces.
- `live.py`: run optional live OpenCode/OpenWebUI end-to-end checks.

### Dataset directories

```text
benchmarks/
  public/
    synthetic_memory_cases.json
  private/
    .gitkeep

benchmark-results/
  .gitkeep
```

Git ignore rules:

```text
benchmarks/private/*
!benchmarks/private/.gitkeep

benchmark-results/*
!benchmark-results/.gitkeep
```

If public benchmark snapshots should be published, copy them deliberately into docs, for example:

```text
docs/benchmarks/public-latest-report.md
docs/benchmarks/public-latest-results.json
```

Do not automatically commit volatile benchmark output.

## Benchmark Modes

### Quick mode

`quick` is the stable default. It must be reproducible and safe for public GitHub claims.

Scope:

- Core retrieval benchmark against isolated temporary Mnémlet storage.
- REST recall/ingest checks.
- Optional adapter-level checks for OpenWebUI and OpenCode.
- No browser automation required.
- No dependence on Christoph's live memory database.

Example commands:

```bash
mnemlet benchmark quick --dataset public
mnemlet benchmark quick --dataset public --include-adapters
mnemlet benchmark quick --dataset private
```

### Full mode

`full` includes real integration flows and may be slower or more fragile.

Scope:

- Everything from quick mode.
- Live OpenCode checks, including `opencode mcp list` and sentinel `opencode run` prompts.
- Optional OpenWebUI live checks against the running user service.
- No OpenWebUI restart, kill, migration, or destructive service action.

Example commands:

```bash
mnemlet benchmark full --dataset public
mnemlet benchmark full --dataset private
```

Full-mode results must be labeled as environment-dependent.

## CLI Design

Add benchmark commands to Mnémlet's CLI:

```bash
mnemlet benchmark quick --dataset public
mnemlet benchmark quick --dataset private
mnemlet benchmark quick --dataset public --include-adapters

mnemlet benchmark full --dataset public
mnemlet benchmark full --dataset private
```

Options:

```text
--output benchmark-results/latest
--format json,md,csv
--min-score 0.1
--limit 5
--include-adapters
--include-live-opencode
--include-live-openwebui
```

The CLI should fail clearly for missing private datasets and should never create private benchmark files automatically from live data without an explicit command.

## Public Dataset Model

Public benchmark data must be synthetic and realistic. A case contains memories, queries, expected memory IDs, optional forbidden memory IDs, and category metadata.

Example:

```json
{
  "id": "fact_exact_nebelkraehe",
  "category": "exact_fact",
  "namespace": "integration/sentinel",
  "memories": [
    {
      "id": "memory_bridge_codename",
      "content": "Christoph calls the Mnémlet OpenCode bridge Nebelkrähe.",
      "importance": 0.95,
      "tags": ["expected"]
    },
    {
      "id": "memory_bridge_noise",
      "content": "OpenCode can connect to external tools through MCP servers.",
      "importance": 0.4,
      "tags": ["distractor"]
    }
  ],
  "queries": [
    {
      "query": "What is the Mnémlet OpenCode bridge called?",
      "expected_memory_ids": ["memory_bridge_codename"],
      "forbidden_memory_ids": ["memory_bridge_noise"],
      "min_expected_rank": 1
    }
  ]
}
```

Benchmark memory IDs are logical IDs. The runner maps them to real Mnémlet memory IDs after ingest.

### Public case categories

Start with roughly 40-60 public queries across these categories:

1. `exact_fact`: direct fact recall.
2. `paraphrase`: query uses different wording than the memory.
3. `namespace_isolation`: similar facts exist in different namespaces.
4. `distractor_resistance`: semantically nearby but wrong memories compete with the expected result.
5. `no_hit`: query should not produce a confident result above the score threshold.
6. `recency_decay_sanity`: cold/deleted/stale memories should not dominate fresh relevant ones.
7. `multi_memory_context`: multiple expected memories should appear in top K.
8. `integration_sentinel`: Nebelkrähe/OpenWebUI/OpenCode/MCP sentinel facts.

## Private Dataset Model

Private real-world benchmark data lives in:

```text
benchmarks/private/real_world_cases.json
```

It must not be committed.

The format can be slightly looser than the public dataset and may use substrings/namespaces when exact memory IDs are inconvenient:

```json
{
  "source": "local_mnemlet",
  "query": "Was war der letzte Stand zur OpenWebUI Integration?",
  "expected_substrings": ["OpenWebUI", "Nebelkrähe", "mnemlet connected"],
  "expected_namespaces": ["projects/mnemlet", "integration/sentinel"]
}
```

Private benchmark reports may be generated locally but should not be committed unless explicitly anonymized and reviewed.

## Metrics

### Retrieval metrics

- `hit@1`, `hit@3`, `hit@5`: whether at least one expected memory appears in the top K.
- `mrr`: mean reciprocal rank of the first expected memory.
- `precision@k`: proportion of top-K results that are expected memories.
- `false_positive_rate`: for no-hit cases, proportion that returned any result above threshold.
- `forbidden_hit_rate`: proportion of cases where forbidden distractor memories appeared.

### Performance metrics

- `latency_ms` per query.
- `p50_latency_ms`.
- `p95_latency_ms`.
- `max_latency_ms`.
- Optional `queries_per_second`.

Reports must include enough environment information to interpret latency:

- hardware class, such as Raspberry Pi 5 16GB when run on `mira-pi`;
- Python version;
- Mnémlet version or git commit;
- storage backend summary;
- dataset name and query count.

### Integration metrics

REST:

- ingest success rate;
- recall success rate;
- response schema validity;
- expected memory returned.

MCP:

- initialize success;
- tool list success;
- `mnemlet_recall` success;
- expected memory returned.

OpenWebUI adapter-level:

- filter `inlet()` injects a system context block;
- expected memory appears in the context block;
- filter `outlet()` stores a compact summary;
- Mnémlet-down scenario remains crash-free and preserves the body.

OpenCode adapter-level:

- query extraction works;
- REST recall is called;
- context block formatting includes expected memory;
- REST fallback tool output contains expected memory;
- timeout/down scenario remains crash-free.

## Report Outputs

### JSON

`results.json` is the complete machine-readable report.

Example shape:

```json
{
  "run_id": "2026-05-21T09-30-00Z",
  "mode": "quick",
  "dataset": "public",
  "hardware": "Raspberry Pi 5 16GB",
  "summary": {
    "hit_at_1": 0.94,
    "hit_at_3": 0.98,
    "mrr": 0.96,
    "false_positive_rate": 0.02,
    "p50_latency_ms": 42,
    "p95_latency_ms": 110
  },
  "cases": []
}
```

### Markdown

`report.md` is the human-readable report.

It must include:

- summary table;
- methodology;
- dataset details;
- hardware/software environment;
- retrieval metrics;
- integration metrics;
- latency metrics;
- failed cases;
- limitations;
- exact command used.

### CSV

`results.csv` has one row per query for later charting and trend analysis.

## GitHub Claim Policy

Only publish claims directly backed by a committed or attached report.

Good claim:

> On the included public benchmark, Mnémlet achieved 96% hit@3 with p95 recall latency under 120ms on a Raspberry Pi 5 16GB.

Bad claim:

> Best local AI memory engine.

The public README should use conservative wording plus exact measured metrics. Stronger marketing copy can be derived later if the data supports it.

## Testing Strategy

### Package 1: Sleep Engine fix

Tests:

- `should_sleep()` is true after the inactivity threshold.
- After a successful run, `should_sleep()` is not immediately true again.
- Checkpoints are reset or scoped per run.
- Activity bump enables a later sleep cycle.
- Parallel runs are prevented.
- Status exposes meaningful state.

Acceptance:

- no repeated empty sleep loop;
- all sleep unit tests pass;
- existing API tests pass.

### Package 2: Benchmark core and public dataset

Tests:

- dataset parser validates required fields;
- duplicate logical IDs are rejected;
- public dataset loads;
- isolated DB/Chroma/Vault are created;
- logical benchmark memory IDs map to real Mnémlet memory IDs;
- query execution records ranks, scores, and latency.

Acceptance:

- `mnemlet benchmark quick --dataset public --retrieval-only` produces JSON;
- live data is not touched.

### Package 3: Metrics and reports

Tests:

- `hit@k`, `precision@k`, `mrr`, false-positive rate, and forbidden-hit rate are correct for known fixtures;
- Markdown report contains summary, methodology, environment, failures, and limitations;
- CSV contains one row per query.

Acceptance:

- `results.json`, `report.md`, and `results.csv` are generated.

### Package 4: Adapter-level OpenWebUI/OpenCode

Tests:

- OpenWebUI filter `inlet()` injects expected context;
- OpenWebUI filter `outlet()` ingests summary;
- OpenWebUI filter fails closed when Mnémlet is unavailable;
- OpenCode harness checks recall, context formatting, tool output, and timeout/down behavior.

Acceptance:

- quick mode can include adapter checks;
- adapter results appear in the report.

### Package 5: Full E2E benchmarks

Checks:

- `opencode mcp list` shows Mnémlet connected;
- `opencode run` returns expected sentinel answers;
- optional OpenWebUI live checks work without restarting or killing the user service.

Acceptance:

- full mode creates a separate environment-labeled report.

### Package 6: GitHub readiness

Checks:

- README benchmark section added;
- `.gitignore` protects private datasets and volatile reports;
- light secret scan before any public commit/push;
- public benchmark snapshot committed only intentionally;
- tests and benchmark commands verified before claims.

## Implementation Pause Gates

Implementation must pause and wait for Christoph after each package:

1. Sleep Engine fix and tests.
2. Benchmark core and public dataset.
3. Metrics and reports.
4. Adapter-level OpenWebUI/OpenCode.
5. Full E2E benchmarks.
6. GitHub readiness.

Before each package commit, summarize exactly what will be committed. After each package, run relevant verification, report evidence, and wait for `Weiter geht's` or equivalent.

## Risks and Mitigations

### Risk: synthetic benchmark overfits to Mnémlet

Mitigation: include distractors, paraphrases, namespace isolation, no-hit cases, and private real-world cases.

### Risk: public claims become too broad

Mitigation: enforce the GitHub claim policy and include methodology/limitations in reports.

### Risk: OpenWebUI live tests disrupt Christoph's active instance

Mitigation: full-mode OpenWebUI checks must be optional and non-destructive. No restart, kill, or migration is allowed.

### Risk: private data leaks

Mitigation: ignore `benchmarks/private/` and volatile `benchmark-results/`; do not copy private outputs into docs without explicit review.

### Risk: benchmark results depend on hardware

Mitigation: always record environment and treat latency as hardware-specific.

### Risk: Codex/OpenCode usage limits interrupt work

Mitigation: pause gates after each design/implementation package and before long-running full benchmarks.

## Out of Scope for This Iteration

- HTML dashboard with charts.
- SaaS/cloud evaluation.
- LLM-as-judge grading.
- Automatic public publishing of benchmark results.
- OpenWebUI service restarts or destructive runtime changes.
- Claims that Mnémlet is globally best-in-class.

## Success Criteria

The implementation is complete when:

- the Sleep Engine no longer repeatedly starts empty consolidation runs after one idle period;
- public benchmark quick mode runs against isolated storage;
- quick mode produces JSON, Markdown, and CSV reports;
- retrieval metrics include hit@K, MRR, precision@K, false-positive rate, forbidden-hit rate, and latency percentiles;
- adapter-level OpenCode/OpenWebUI checks can be included in quick mode;
- full mode can run live OpenCode checks and optional non-destructive OpenWebUI checks;
- private benchmark data remains uncommitted;
- README claims are backed by generated public benchmark evidence;
- all relevant tests pass before each implementation package is considered complete.
