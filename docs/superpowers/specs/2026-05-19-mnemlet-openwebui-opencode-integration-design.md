# Mnémlet OpenWebUI + OpenCode Integration Design

Date: 2026-05-19
Status: Approved design, pending implementation plan

## Goal

Mnémlet should provide working memory context in both active chat surfaces Christoph uses:

- OpenWebUI chat should automatically inject relevant Mnémlet context before the model answers and store useful chat summaries afterward.
- OpenCode chat should get Mnémlet context automatically through a plugin and explicit memory tools through MCP.

The existing, currently used OpenWebUI instance must remain untouched at runtime unless Christoph explicitly approves a restart or reload.

## Current Evidence

### Mnémlet

- Mnémlet runs on `http://localhost:4050`.
- REST endpoints are working:
  - `GET /api/v1/status`
  - `POST /api/v1/recall`
  - `POST /api/v1/ingest`
- The service is managed as a user systemd service: `mnemlet.service`.
- Current status endpoint reports active memories and Chroma documents.

### OpenWebUI

- The active OpenWebUI instance is the user service `open-webui.service`.
- It listens on `127.0.0.1:8080` and uses `/home/christoph/mira/data`.
- Christoph is actively using this instance. It must not be stopped, replaced, or migrated.
- A separate system service, `openwebui.service`, also tries to bind to `127.0.0.1:8080` and fails in a restart loop with `address already in use`.
- The Mnémlet filter is registered in OpenWebUI's SQLite DB as:
  - name: `Mnémlet Memory`
  - type: `filter`
  - active: true
  - global: true
- Manual OpenWebUI loader reproduction with the service environment loaded the DB content as a `Filter` successfully. The earlier `No Function class found` error was not reproducible with the current DB content.
- Direct `inlet()` testing injects relevant Mnémlet memories into a system message.

### OpenCode

- Installed OpenCode version is `1.14.48`.
- OpenCode supports MCP via `opencode mcp`.
- Current OpenCode MCP config only shows `tavily` connected.
- A stale `/home/christoph/.config/opencode/mcp.json` has a Mnémlet MCP entry, but OpenCode's active config uses `/home/christoph/.config/opencode/config.json`.
- Mnémlet's `/mcp/` endpoint currently fails with HTTP 500:
  - `RuntimeError: Task group is not initialized. Make sure to use run().`
- Root cause: FastMCP's streamable HTTP Starlette app is mounted without its lifespan/session manager being started.

## Architecture

Mnémlet remains the single memory engine. OpenWebUI and OpenCode integrate through different adapters.

```text
Mnémlet REST API :4050
├─ OpenWebUI Filter
│  ├─ inlet: recall → inject context as system message
│  └─ outlet: summarize/store interaction
│
├─ Mnémlet MCP
│  └─ OpenCode MCP tools: recall, ingest, status, namespaces, etc.
│
└─ OpenCode Plugin
   ├─ automatic context injection through OpenCode hooks
   └─ REST fallback tools for recall/ingest
```

## OpenWebUI Design

The active user service `open-webui.service` remains the official OpenWebUI instance for this work.

The broken system-level `openwebui.service` should be disabled or masked because it only conflicts with the running instance. This change is reversible and does not touch the active OpenWebUI process.

The existing filter should remain a normal OpenWebUI `Filter` class with `inlet()` and `outlet()` methods:

1. `inlet()` reads the latest user message.
2. It calls `POST /api/v1/recall` with a small result limit.
3. It prepends a bounded system context block if memories are found.
4. It returns the modified request body.
5. `outlet()` extracts the latest user/assistant pair.
6. It calls `POST /api/v1/ingest` with a concise interaction summary.

The filter should be defensive:

- Mnémlet unavailable: log and return the original body.
- Empty recall: return the original body.
- Missing fields in memory results: use `.get()` defaults.
- Ingest failure: log and preserve the assistant response.

The file `/home/christoph/mira/data/functions/mnemlet_valve.py` and the DB-registered function content should be kept in sync after any edit.

## Mnémlet MCP Design

Mnémlet should continue exposing its eight MCP tools, but the FastMCP streamable HTTP lifecycle must be fixed.

The fix should ensure the FastMCP session manager is running when requests hit `/mcp/`. The implementation plan must preserve the lifespan of the Starlette app returned by `mcp.streamable_http_app()` instead of mounting only its request handler without startup. If Starlette's mounted lifespan does not run in the current FastAPI version, Mnémlet must explicitly enter the MCP app lifespan during Mnémlet startup and exit it during shutdown.

Success criteria:

- `/mcp/` no longer returns 500 due to an uninitialized task group.
- `opencode mcp list` shows Mnémlet as connected after configuration.
- Existing REST endpoints continue to work.
- Existing Mnémlet tests continue to pass.

## OpenCode Plugin Design

OpenCode should get both automatic and explicit memory access.

The plugin will live under `/home/christoph/.config/opencode/plugins/` and must not modify or break the existing `claude-mem-observer.js` plugin.

The plugin should:

1. Call Mnémlet REST `/api/v1/recall` for the current prompt/session context.
2. Inject a bounded memory block into OpenCode's system context through `experimental.chat.system.transform`.
3. Track the latest user text per session through `chat.message` if the system transform hook does not receive enough prompt text directly.
4. Provide fallback tools such as `mnemlet_recall` and `mnemlet_ingest` using REST, so memory remains usable even if automatic injection is limited by OpenCode hook data.
5. Fail open: if Mnémlet is unreachable, OpenCode should continue normally without memory context.

Configuration should be added to the active OpenCode config, `/home/christoph/.config/opencode/config.json`, not only to the stale `mcp.json` file.

## Data Flow

### OpenWebUI Chat

```text
User message
→ OpenWebUI Filter.inlet()
→ Mnémlet /api/v1/recall
→ context system message injected
→ model response
→ OpenWebUI Filter.outlet()
→ Mnémlet /api/v1/ingest
```

### OpenCode MCP

```text
OpenCode MCP client
→ Mnémlet /mcp/
→ MCP tool call
→ Mnémlet engine
→ tool result returned to OpenCode
```

### OpenCode Plugin

```text
OpenCode user message
→ plugin hook
→ Mnémlet /api/v1/recall
→ bounded memory context appended to system prompt
→ model response uses memory context
```

## Error Handling

- All integrations fail open. Memory failure must not block chat usage.
- Context injection is bounded by result count and text length.
- Runtime service changes avoid touching the active OpenWebUI process.
- Any database or config file edit gets a backup first.

## Tests and Verification

### Mnémlet Automated Tests

- Add or update a test covering MCP startup/lifespan behavior.
- Existing test suite must remain green.
- REST smoke tests:
  - `GET /api/v1/status`
  - `POST /api/v1/ingest`
  - `POST /api/v1/recall`

### OpenWebUI Verification

- Export current DB function content before changes.
- Load the registered function content with OpenWebUI's `load_function_module_by_id()`.
- Verify it returns a `filter` object with `inlet` and `outlet`.
- Test `inlet()` directly against a known Mnémlet memory.
- Run a live OpenWebUI chat asking about a known memory and confirm the answer uses injected context.
- Confirm no `No Function class found` errors appear in the user service logs.

### OpenCode Verification

- `opencode mcp list` shows Mnémlet connected.
- A direct Mnémlet MCP recall/status tool call works.
- `opencode run` with a known-memory question produces an answer using Mnémlet context.
- REST fallback tools in the plugin return expected recall/ingest results.

## Rollback

### OpenWebUI

- Restore exported function DB content.
- Or set the Mnémlet function `is_active=0`.
- Do not stop the active `open-webui.service` unless Christoph explicitly approves.

### systemd

- Re-enable/unmask the system `openwebui.service` if needed.
- The active user `open-webui.service` remains unchanged.

### OpenCode

- Remove the Mnémlet plugin file.
- Restore the previous `/home/christoph/.config/opencode/config.json`.
- Remove the Mnémlet MCP entry.

### Mnémlet

- Revert the Mnémlet git changes.
- Restart `mnemlet.service` only after approval or during planned deployment.

## Out of Scope

- Search quality changes.
- New authentication or multi-user support.
- OpenWebUI UI/theme migration.
- Mnémlet website changes.
- Large refactors unrelated to the integration.
