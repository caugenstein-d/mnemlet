# Mnémlet OpenWebUI + OpenCode Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Mnémlet memory work end-to-end in Christoph's active OpenWebUI instance and in OpenCode through both MCP tools and automatic REST-backed context injection.

**Architecture:** Mnémlet remains the single memory engine on `http://localhost:4050`. OpenWebUI uses a defensive `Filter` function stored in its active DB and mirrored in `/home/christoph/mira/data/functions/mnemlet_valve.py`; OpenCode uses repaired Mnémlet MCP plus a local plugin in `/home/christoph/.config/opencode/plugins/`.

**Tech Stack:** Python 3.12, FastAPI, Starlette lifespan, FastMCP, pytest/httpx, OpenWebUI v0.9.5, OpenCode 1.14.48 plugins, systemd user/system units.

---

## File Structure

### Mnémlet repository: `/home/christoph/mnemlet`

- Modify: `src/mnemlet/server/app.py`
  - Responsibility: create the FastAPI app, mount the MCP app once, explicitly enter the MCP app lifespan while Mnémlet is running, keep REST routes unchanged.
- Create: `tests/test_mcp.py`
  - Responsibility: verify Mnémlet starts FastMCP's streamable HTTP session manager during application lifespan and shuts it down afterward.
- Existing: `docs/superpowers/specs/2026-05-19-mnemlet-openwebui-opencode-integration-design.md`
  - Responsibility: approved design reference for this plan.

### Active OpenWebUI runtime: `/home/christoph/mira`

- Modify: `/home/christoph/mira/data/functions/mnemlet_valve.py`
  - Responsibility: defensive OpenWebUI `Filter` implementation for Mnémlet recall/inject and ingest/outlet.
- Modify via SQLite: `/home/christoph/mira/data/webui.db`
  - Responsibility: store the active OpenWebUI Function content for `Mnémlet Memory`.
- Do not modify or restart without explicit approval: `systemctl --user open-webui.service`
  - Responsibility: Christoph's active OpenWebUI instance.

### OpenCode config/runtime: `/home/christoph/.config/opencode`

- Create: `/home/christoph/.config/opencode/plugins/mnemlet-memory.js`
  - Responsibility: OpenCode plugin that recalls Mnémlet context via REST, injects context into system prompts, and exposes REST fallback tools.
- Modify: `/home/christoph/.config/opencode/config.json`
  - Responsibility: add active Mnémlet MCP server config while preserving existing model, agent, and Tavily settings.
- Preserve: `/home/christoph/.config/opencode/plugins/claude-mem-observer.js`
  - Responsibility: existing observer plugin; do not change it.

### systemd units

- Disable/mask: `/etc/systemd/system/openwebui.service`
  - Responsibility: broken duplicate system service currently failing on port `8080`.
- Preserve: `/home/christoph/.config/systemd/user/open-webui.service`
  - Responsibility: active OpenWebUI service Christoph is using.
- Restart after tests: `systemctl --user restart mnemlet.service`
  - Responsibility: deploy repaired Mnémlet MCP server.

---

## Task 1: Capture Runtime Backups and Remove the Duplicate OpenWebUI System Service

**Files:**
- Backup: `/home/christoph/mira/data/functions/mnemlet_valve.py`
- Backup: OpenWebUI DB function content from `/home/christoph/mira/data/webui.db`
- Modify systemd state: disable/mask `openwebui.service`
- Preserve: `systemctl --user open-webui.service`

- [ ] **Step 1: Verify the active OpenWebUI user service is still running**

Run:

```bash
systemctl --user status 'open-webui.service' --no-pager --full
```

Expected: output includes `Active: active (running)` and an `ExecStart` using `/home/christoph/mira/.venv/bin/open-webui serve --host 127.0.0.1 --port 8080`.

- [ ] **Step 2: Verify the duplicate system service is the failing one**

Run:

```bash
systemctl status 'openwebui.service' --no-pager --full
```

Expected: output shows `openwebui.service` as failed, activating, or restarting, and recent logs mention port `8080` / `address already in use`.

- [ ] **Step 3: Create backup directory**

Run:

```bash
mkdir -p '/home/christoph/mira/data/functions/backups'
```

Expected: no output and exit code `0`.

- [ ] **Step 4: Backup the current OpenWebUI filter file**

Run:

```bash
ts="$(date +%Y%m%d-%H%M%S)" && cp '/home/christoph/mira/data/functions/mnemlet_valve.py' "/home/christoph/mira/data/functions/backups/mnemlet_valve.py.${ts}.bak" && ls -l "/home/christoph/mira/data/functions/backups/mnemlet_valve.py.${ts}.bak"
```

Expected: `ls -l` shows one backup file with non-zero size.

- [ ] **Step 5: Backup the DB-registered OpenWebUI function content**

Run:

```bash
/home/christoph/mira/.venv/bin/python - <<'PY'
from pathlib import Path
import sqlite3
import time

db_path = Path('/home/christoph/mira/data/webui.db')
backup_dir = Path('/home/christoph/mira/data/functions/backups')
backup_dir.mkdir(parents=True, exist_ok=True)
backup_path = backup_dir / f'mnemlet_function_db_content.{time.strftime("%Y%m%d-%H%M%S")}.py'

con = sqlite3.connect(db_path)
row = con.execute(
    "SELECT content FROM function WHERE name = ? AND type = ?",
    ('Mnémlet Memory', 'filter'),
).fetchone()
if row is None:
    raise SystemExit('Mnémlet Memory filter not found in OpenWebUI DB')
backup_path.write_text(row[0], encoding='utf-8')
print(backup_path)
PY
```

Expected: prints a path under `/home/christoph/mira/data/functions/backups/`.

- [ ] **Step 6: Disable and stop only the broken system service**

Run:

```bash
sudo systemctl disable --now 'openwebui.service'
```

Expected: systemd reports that the unit was disabled/stopped, or no output with exit code `0`. If sudo asks for a password, stop this task and ask Christoph to run the command.

- [ ] **Step 7: Mask the broken system service so it does not restart on boot**

Run:

```bash
sudo systemctl mask 'openwebui.service'
```

Expected: output includes `Created symlink` or confirms the unit is masked. If sudo asks for a password, stop this task and ask Christoph to run the command.

- [ ] **Step 8: Confirm the active OpenWebUI user service survived**

Run:

```bash
systemctl --user status 'open-webui.service' --no-pager --full
```

Expected: output still includes `Active: active (running)`.

- [ ] **Step 9: Confirm port 8080 belongs to the active user service process**

Run:

```bash
ss -ltnp 'sport = :8080'
```

Expected: output shows one listener on `127.0.0.1:8080` from a Python/OpenWebUI process.

- [ ] **Step 10: Commit operational notes only if commits are explicitly approved**

Run only after Christoph explicitly approves committing in this session:

```bash
git status --short
git add docs/superpowers/specs/2026-05-19-mnemlet-openwebui-opencode-integration-design.md docs/superpowers/plans/2026-05-19-mnemlet-openwebui-opencode-integration.md
git commit -m "docs: plan Mnémlet OpenWebUI and OpenCode integration"
```

Expected: commit succeeds. If commits are not approved, skip this step and continue without committing.

---

## Task 2: Add a Failing Test for Mnémlet MCP Lifespan Startup

**Files:**
- Create: `/home/christoph/mnemlet/tests/test_mcp.py`
- Uses: `/home/christoph/mnemlet/src/mnemlet/server/app.py`

- [ ] **Step 1: Write the failing MCP lifespan test**

Create `/home/christoph/mnemlet/tests/test_mcp.py` with this complete content:

```python
"""Integration tests for the MCP server lifecycle."""

import tempfile
from pathlib import Path

import pytest

from mnemlet.config import MnemletConfig
from mnemlet.server.app import create_app


def _test_config(base: Path) -> MnemletConfig:
    """Build an isolated config for MCP tests."""
    return MnemletConfig(
        data_dir=base,
        sqlite_path=base / "mnemlet.db",
        chroma_path=base / "chroma",
        vault_path=base / "vault",
        embedding_cache_dir=base / "models",
    )


@pytest.mark.asyncio
async def test_mcp_session_manager_starts_during_app_lifespan() -> None:
    """FastMCP's streamable HTTP session manager is active during app lifespan."""
    with tempfile.TemporaryDirectory() as tmpdir:
        app = create_app(_test_config(Path(tmpdir)))

        assert hasattr(app.state, "mcp_session_manager")
        assert app.state.mcp_session_manager._task_group is None

        async with app.router.lifespan_context(app):
            assert app.state.mcp_session_manager._task_group is not None

        assert app.state.mcp_session_manager._task_group is None
```

- [ ] **Step 2: Run the new test and verify it fails**

Run:

```bash
/home/christoph/mnemlet/.venv/bin/python -m pytest tests/test_mcp.py -q
```

Expected: FAIL. The failure should be an assertion or attribute error showing `mcp_session_manager` is missing or its `_task_group` never starts.

- [ ] **Step 3: Run the existing API tests as a baseline**

Run:

```bash
/home/christoph/mnemlet/.venv/bin/python -m pytest tests/test_api.py -q
```

Expected: PASS. If this fails, stop and investigate before modifying the MCP implementation.

---

## Task 3: Fix Mnémlet MCP Lifespan Without Breaking REST

**Files:**
- Modify: `/home/christoph/mnemlet/src/mnemlet/server/app.py`
- Test: `/home/christoph/mnemlet/tests/test_mcp.py`
- Regression: `/home/christoph/mnemlet/tests/test_api.py`

- [ ] **Step 1: Replace `app.py` with explicit MCP app lifespan management**

Update `/home/christoph/mnemlet/src/mnemlet/server/app.py` to this complete content:

```python
"""FastAPI application factory."""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AsyncExitStack, asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import Response

from mnemlet.config import MnemletConfig
from mnemlet.engine.decay import DecayEngine
from mnemlet.engine.ingest import IngestEngine
from mnemlet.engine.recall import RecallEngine
from mnemlet.engine.sleep import SleepEngine
from mnemlet.server.mcp_server import create_mcp_server
from mnemlet.server.routes import decay, ingest, recall, sleep, status
from mnemlet.storage.chroma import MnemletChroma
from mnemlet.storage.embeddings import MnemletEmbedding
from mnemlet.storage.sqlite import MnemletDB
from mnemlet.storage.vault import VaultWriter


def _get_mcp_session_manager(mcp_app: Any) -> Any:
    """Return the FastMCP streamable HTTP session manager from the mounted app."""
    for route in getattr(mcp_app, "routes", []):
        endpoint = getattr(route, "endpoint", None)
        session_manager = getattr(endpoint, "session_manager", None)
        if session_manager is not None:
            return session_manager
    raise RuntimeError("FastMCP streamable HTTP session manager not found")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup and shutdown lifecycle."""
    config = app.state.config
    app.state.db = MnemletDB(config.sqlite_path)
    app.state.embedder = MnemletEmbedding(cache_dir=config.embedding_cache_dir)
    app.state.chroma = MnemletChroma(config.chroma_path, app.state.embedder)
    app.state.vault = VaultWriter(config.vault_path)
    app.state.ingest_engine = IngestEngine(
        db=app.state.db,
        chroma=app.state.chroma,
        embedder=app.state.embedder,
        vault=app.state.vault,
    )
    app.state.recall_engine = RecallEngine(
        db=app.state.db,
        chroma=app.state.chroma,
        embedder=app.state.embedder,
    )

    decay_engine = DecayEngine(app.state.db)
    app.state.sleep_engine = SleepEngine(
        db=app.state.db,
        chroma=app.state.chroma,
        embedder=app.state.embedder,
        vault=app.state.vault,
        decay_engine=decay_engine,
    )

    async def decay_loop() -> None:
        """Run decay processing every 6 hours."""
        while True:
            await asyncio.sleep(6 * 3600)
            try:
                result = decay_engine.decay_all_active(limit=500)
                print(
                    f"[decay] processed={result['processed']} "
                    f"decayed={result['decayed']} "
                    f"cold={result['moved_to_cold']} "
                    f"deleted={result['hard_deleted']}"
                )
            except Exception as e:
                print(f"[decay] error: {e}")

    async def sleep_monitor() -> None:
        """Check inactivity and trigger sleep phase."""
        while True:
            await asyncio.sleep(300)
            if app.state.sleep_engine.should_sleep():
                print("[sleep] Inactivity threshold reached, starting consolidation...")
                app.state.sleep_engine.start()

    async with AsyncExitStack() as stack:
        await stack.enter_async_context(app.state.mcp_app.router.lifespan_context(app.state.mcp_app))
        decay_task = asyncio.create_task(decay_loop())
        sleep_task = asyncio.create_task(sleep_monitor())
        try:
            yield
        finally:
            decay_task.cancel()
            sleep_task.cancel()
            try:
                await decay_task
            except asyncio.CancelledError:
                pass
            try:
                await sleep_task
            except asyncio.CancelledError:
                pass


def create_app(config: MnemletConfig | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    if config is None:
        config = MnemletConfig()

    app = FastAPI(
        title="Mnemlet",
        description="Self-hosted, brain-inspired memory engine for AI agents.",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.config = config

    mcp = create_mcp_server(app.state)
    mcp_app = mcp.streamable_http_app()
    app.state.mcp = mcp
    app.state.mcp_app = mcp_app
    app.state.mcp_session_manager = _get_mcp_session_manager(mcp_app)
    app.mount("/mcp", mcp_app)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def track_activity(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        """Bump sleep engine activity on every API call."""
        if hasattr(request.app.state, "sleep_engine"):
            request.app.state.sleep_engine.bump_activity()
        response = await call_next(request)
        return response

    app.include_router(decay.router)
    app.include_router(ingest.router)
    app.include_router(recall.router)
    app.include_router(sleep.router)
    app.include_router(status.router)

    return app
```

- [ ] **Step 2: Run the MCP test and verify it passes**

Run:

```bash
/home/christoph/mnemlet/.venv/bin/python -m pytest tests/test_mcp.py -q
```

Expected: PASS.

- [ ] **Step 3: Run REST API regression tests**

Run:

```bash
/home/christoph/mnemlet/.venv/bin/python -m pytest tests/test_api.py -q
```

Expected: PASS.

- [ ] **Step 4: Run the full Mnémlet test suite**

Run:

```bash
/home/christoph/mnemlet/.venv/bin/python -m pytest -q
```

Expected: all tests pass.

- [ ] **Step 5: Restart Mnémlet user service to deploy the MCP fix**

Run:

```bash
systemctl --user restart 'mnemlet.service'
```

Expected: no output and exit code `0`.

- [ ] **Step 6: Verify Mnémlet service is running**

Run:

```bash
systemctl --user status 'mnemlet.service' --no-pager --full
```

Expected: `Active: active (running)`.

- [ ] **Step 7: Verify REST status after restart**

Run:

```bash
curl -sS 'http://localhost:4050/api/v1/status'
```

Expected: JSON containing `active_memories`, `total_interactions`, and `version`.

- [ ] **Step 8: Verify `/mcp/` no longer fails with the task-group root cause**

Run:

```bash
curl --max-time 10 -sS -i -X POST 'http://localhost:4050/mcp/' \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  --data '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"curl-smoke","version":"0.1.0"}}}'
```

Expected: response is not `500 Internal Server Error`, and the body does not contain `Task group is not initialized`.

- [ ] **Step 9: Commit Mnémlet code only if commits are explicitly approved**

Run only after Christoph explicitly approves committing in this session:

```bash
git add src/mnemlet/server/app.py tests/test_mcp.py
git commit -m "fix: start Mnémlet MCP lifespan"
```

Expected: commit succeeds. If commits are not approved, skip this step and continue without committing.

---

## Task 4: Harden and Sync the OpenWebUI Mnémlet Filter

**Files:**
- Modify: `/home/christoph/mira/data/functions/mnemlet_valve.py`
- Modify via SQLite: `/home/christoph/mira/data/webui.db`
- Preserve: `systemctl --user open-webui.service`

- [ ] **Step 1: Replace the filter file with the defensive implementation**

Write this complete content to `/home/christoph/mira/data/functions/mnemlet_valve.py`:

```python
"""
Mnémlet Memory Filter for OpenWebUI.
title: Mnémlet Memory
author: Christoph + Mira
version: 1.1.0
"""

import json
from typing import Any
import urllib.error
import urllib.request

MNEMLET_URL = "http://localhost:4050"
RECALL_LIMIT = 3
RECALL_TIMEOUT_SECONDS = 3
INGEST_TIMEOUT_SECONDS = 3
MAX_MEMORY_CONTENT_CHARS = 800
MAX_STORED_MESSAGE_CHARS = 200


def _post_json(path: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    """POST JSON to Mnémlet and return a JSON object."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{MNEMLET_URL}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
    parsed = json.loads(raw) if raw else {}
    return parsed if isinstance(parsed, dict) else {}


def _latest_user_content(messages: list[dict[str, Any]]) -> str:
    """Return the latest user message content from an OpenWebUI message list."""
    for message in reversed(messages):
        if message.get("role") == "user":
            content = message.get("content", "")
            return content if isinstance(content, str) else ""
    return ""


def _latest_assistant_content(messages: list[dict[str, Any]]) -> str:
    """Return the latest assistant message content from an OpenWebUI message list."""
    for message in reversed(messages):
        if message.get("role") == "assistant":
            content = message.get("content", "")
            return content if isinstance(content, str) else ""
    return ""


def _format_memories(memories: list[dict[str, Any]]) -> str:
    """Format Mnémlet recall results as a bounded system context block."""
    lines = []
    for memory in memories[:RECALL_LIMIT]:
        namespace = memory.get("namespace") or "default"
        content = memory.get("content") or memory.get("content_preview") or ""
        if not isinstance(content, str) or not content.strip():
            continue
        clipped = content.strip()[:MAX_MEMORY_CONTENT_CHARS]
        lines.append(f"[{namespace}] {clipped}")

    if not lines:
        return ""

    return (
        "--- Relevant context from Mnémlet memory ---\n"
        + "\n".join(lines)
        + "\n---\n"
    )


class Filter:
    """OpenWebUI filter that bridges chat requests to Mnémlet memory."""

    def __init__(self) -> None:
        self.priority = 0

    def inlet(self, body: dict, __user__: dict | None = None) -> dict:
        """Before the LLM responds, inject relevant Mnémlet memories."""
        try:
            messages = body.get("messages", [])
            if not isinstance(messages, list) or not messages:
                return body

            query = _latest_user_content(messages).strip()
            if len(query) < 3:
                return body

            response = _post_json(
                "/api/v1/recall",
                {"query": query, "limit": RECALL_LIMIT, "min_score": 0.1},
                RECALL_TIMEOUT_SECONDS,
            )
            memories = response.get("results", [])
            if not isinstance(memories, list):
                return body

            context = _format_memories(memories)
            if not context:
                return body

            first_message = messages[0]
            if isinstance(first_message, dict) and first_message.get("role") == "system":
                existing = first_message.get("content", "")
                first_message["content"] = context + "\n" + (existing if isinstance(existing, str) else "")
            else:
                messages.insert(0, {"role": "system", "content": context})
            body["messages"] = messages
        except Exception as e:
            print(f"[Mnémlet inlet] {type(e).__name__}: {e}")

        return body

    def outlet(self, body: dict, __user__: dict | None = None) -> dict:
        """After the LLM responds, store a compact interaction summary."""
        try:
            messages = body.get("messages", [])
            if not isinstance(messages, list):
                return body

            last_user = _latest_user_content(messages)
            last_assistant = _latest_assistant_content(messages)
            if not last_user or not last_assistant:
                return body

            content = (
                f"User: {last_user[:MAX_STORED_MESSAGE_CHARS]}. "
                f"Assistant: {last_assistant[:MAX_STORED_MESSAGE_CHARS]}"
            )
            _post_json(
                "/api/v1/ingest",
                {
                    "content": content,
                    "namespace": "openwebui/christoph/daily_chat",
                    "importance": 0.3,
                },
                INGEST_TIMEOUT_SECONDS,
            )
        except Exception as e:
            print(f"[Mnémlet outlet] {type(e).__name__}: {e}")

        return body
```

- [ ] **Step 2: Syntax-check the filter with OpenWebUI's Python**

Run:

```bash
/home/christoph/mira/.venv/bin/python -m py_compile '/home/christoph/mira/data/functions/mnemlet_valve.py'
```

Expected: no output and exit code `0`.

- [ ] **Step 3: Sync the filter file into OpenWebUI's function DB**

Run:

```bash
DATA_DIR='/home/christoph/mira/data' WEBUI_SECRET_KEY_FILE='/home/christoph/mira/.webui_secret_key' /home/christoph/mira/.venv/bin/python - <<'PY'
from pathlib import Path
import sqlite3
import time

db_path = Path('/home/christoph/mira/data/webui.db')
filter_path = Path('/home/christoph/mira/data/functions/mnemlet_valve.py')
content = filter_path.read_text(encoding='utf-8')

con = sqlite3.connect(db_path)
cur = con.execute(
    "UPDATE function SET content = ?, is_active = 1, is_global = 1, updated_at = ? WHERE name = ? AND type = ?",
    (content, int(time.time()), 'Mnémlet Memory', 'filter'),
)
con.commit()
if cur.rowcount != 1:
    raise SystemExit(f'Expected to update 1 Mnémlet Memory filter, updated {cur.rowcount}')
print('updated Mnémlet Memory filter in OpenWebUI DB')
PY
```

Expected: prints `updated Mnémlet Memory filter in OpenWebUI DB`.

- [ ] **Step 4: Reproduce the OpenWebUI function loader against DB content**

Run:

```bash
DATA_DIR='/home/christoph/mira/data' WEBUI_SECRET_KEY_FILE='/home/christoph/mira/.webui_secret_key' /home/christoph/mira/.venv/bin/python - <<'PY'
import asyncio
import sqlite3

from open_webui.utils.plugin import load_function_module_by_id

db_path = '/home/christoph/mira/data/webui.db'
con = sqlite3.connect(db_path)
row = con.execute(
    "SELECT id, content FROM function WHERE name = ? AND type = ?",
    ('Mnémlet Memory', 'filter'),
).fetchone()
if row is None:
    raise SystemExit('Mnémlet Memory filter not found')
function_id, content = row


async def main() -> None:
    module, function_type, frontmatter = await load_function_module_by_id(function_id, content)
    assert function_type == 'filter'
    assert hasattr(module, 'inlet')
    assert hasattr(module, 'outlet')
    assert frontmatter.get('title') == 'Mnémlet Memory'
    print(f'loaded {function_id} as {function_type}')


asyncio.run(main())
PY
```

Expected: prints `loaded <id> as filter` and does not print `No Function class found`.

- [ ] **Step 5: Verify `inlet()` injects known Mnémlet context**

Run:

```bash
DATA_DIR='/home/christoph/mira/data' WEBUI_SECRET_KEY_FILE='/home/christoph/mira/.webui_secret_key' /home/christoph/mira/.venv/bin/python - <<'PY'
import asyncio
import sqlite3

from open_webui.utils.plugin import load_function_module_by_id

db_path = '/home/christoph/mira/data/webui.db'
row = sqlite3.connect(db_path).execute(
    "SELECT id, content FROM function WHERE name = ? AND type = ?",
    ('Mnémlet Memory', 'filter'),
).fetchone()
function_id, content = row


async def main() -> None:
    module, _, _ = await load_function_module_by_id(function_id, content)
    body = {'messages': [{'role': 'user', 'content': 'Was weißt du über Mnémlet und OpenCode?'}]}
    result = module.inlet(body)
    first = result['messages'][0]
    assert first['role'] == 'system'
    assert 'Mnémlet memory' in first['content']
    assert 'Mnémlet' in first['content'] or 'Mnemlet' in first['content']
    print(first['content'][:500])


asyncio.run(main())
PY
```

Expected: prints a system-context block containing Mnémlet memory text.

- [ ] **Step 6: Verify active OpenWebUI logs have no new function loader errors**

Run:

```bash
journalctl --user -u 'open-webui.service' --since '5 minutes ago' --grep='No Function class\|Error loading module\|Mnémlet inlet\|Mnémlet outlet' --no-pager
```

Expected: either `-- No entries --` or only Mnémlet informational print lines without `No Function class found`.

---

## Task 5: Add Mnémlet MCP to Active OpenCode Config

**Files:**
- Backup: `/home/christoph/.config/opencode/config.json`
- Modify: `/home/christoph/.config/opencode/config.json`

- [ ] **Step 1: Backup OpenCode config**

Run:

```bash
ts="$(date +%Y%m%d-%H%M%S)" && cp '/home/christoph/.config/opencode/config.json' "/home/christoph/.config/opencode/config.json.${ts}.bak" && ls -l "/home/christoph/.config/opencode/config.json.${ts}.bak"
```

Expected: `ls -l` shows one backup file with non-zero size.

- [ ] **Step 2: Add Mnémlet MCP config while preserving existing settings**

Run:

```bash
python - <<'PY'
from pathlib import Path
import json

config_path = Path('/home/christoph/.config/opencode/config.json')
data = json.loads(config_path.read_text(encoding='utf-8'))
mcp = data.setdefault('mcp', {})
mcp['mnemlet'] = {
    'type': 'remote',
    'url': 'http://localhost:4050/mcp/',
}
config_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
print('configured mnemlet MCP')
PY
```

Expected: prints `configured mnemlet MCP`.

- [ ] **Step 3: Validate JSON syntax**

Run:

```bash
python -m json.tool '/home/christoph/.config/opencode/config.json' > /tmp/opencode-config-check.json
```

Expected: no output and exit code `0`.

- [ ] **Step 4: Verify resolved OpenCode config includes Mnémlet MCP**

Run:

```bash
opencode debug config
```

Expected: JSON output contains `"mnemlet"` under `"mcp"` with URL `http://localhost:4050/mcp/`.

- [ ] **Step 5: Verify OpenCode MCP list sees Mnémlet**

Run:

```bash
opencode mcp list
```

Expected: output lists both `tavily` and `mnemlet`. `mnemlet` should be connected after the MCP lifespan fix is deployed.

---

## Task 6: Build the OpenCode Mnémlet Memory Plugin

**Files:**
- Create: `/home/christoph/.config/opencode/plugins/mnemlet-memory.js`
- Preserve: `/home/christoph/.config/opencode/plugins/claude-mem-observer.js`

- [ ] **Step 1: Create the OpenCode plugin file**

Create `/home/christoph/.config/opencode/plugins/mnemlet-memory.js` with this complete content:

```javascript
import { tool } from "@opencode-ai/plugin"

const MNEMLET_URL = process.env.MNEMLET_URL || "http://127.0.0.1:4050"
const DEFAULT_LIMIT = 5
const MAX_QUERY_CHARS = 2000
const MAX_MEMORY_CHARS = 900
const MAX_CONTEXT_CHARS = 3500
const REQUEST_TIMEOUT_MS = 4000
const sessionQueries = new Map()

function clipText(value, maxChars) {
  if (typeof value !== "string") return ""
  return value.trim().slice(0, maxChars)
}

function extractTextFromPart(part) {
  if (!part || typeof part !== "object") return ""
  if (typeof part.text === "string") return part.text
  if (typeof part.content === "string") return part.content
  if (part.type === "text" && typeof part.value === "string") return part.value
  return ""
}

function extractPromptText(output) {
  const parts = Array.isArray(output?.parts) ? output.parts : []
  const partText = parts.map(extractTextFromPart).filter(Boolean).join("\n")
  if (partText.trim()) return clipText(partText, MAX_QUERY_CHARS)

  const message = output?.message || {}
  if (typeof message.content === "string") return clipText(message.content, MAX_QUERY_CHARS)
  if (typeof message.text === "string") return clipText(message.text, MAX_QUERY_CHARS)
  return ""
}

function rememberSessionQuery(sessionID, query) {
  if (!sessionID || !query) return
  sessionQueries.set(sessionID, { query: clipText(query, MAX_QUERY_CHARS), updatedAt: Date.now() })
}

async function postJson(path, payload, timeoutMs = REQUEST_TIMEOUT_MS) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  try {
    const response = await fetch(`${MNEMLET_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: controller.signal,
    })
    const text = await response.text()
    const data = text ? JSON.parse(text) : {}
    if (!response.ok) {
      return { ok: false, error: `HTTP ${response.status}: ${text}` }
    }
    return { ok: true, data }
  } catch (error) {
    return { ok: false, error: error?.message || String(error) }
  } finally {
    clearTimeout(timer)
  }
}

async function recallMemories(query, limit = DEFAULT_LIMIT, namespace = undefined) {
  const payload = { query: clipText(query, MAX_QUERY_CHARS), limit, min_score: 0.1 }
  if (namespace) payload.namespace = namespace
  return postJson("/api/v1/recall", payload)
}

function formatMemoryBlock(data) {
  const results = Array.isArray(data?.results) ? data.results : []
  const lines = []

  for (const memory of results.slice(0, DEFAULT_LIMIT)) {
    const namespace = memory?.namespace || "default"
    const content = clipText(memory?.content || memory?.content_preview || "", MAX_MEMORY_CHARS)
    if (!content) continue
    lines.push(`[${namespace}] ${content}`)
  }

  if (lines.length === 0) return ""

  return clipText(
    [
      "Relevant context from Mnémlet memory:",
      ...lines,
      "Use this only when it helps answer the user's current request.",
    ].join("\n"),
    MAX_CONTEXT_CHARS,
  )
}

function formatRecallToolOutput(data) {
  const results = Array.isArray(data?.results) ? data.results : []
  if (results.length === 0) return "No Mnémlet memories matched."
  return results
    .map((memory, index) => {
      const namespace = memory?.namespace || "default"
      const score = typeof memory?.score === "number" ? memory.score.toFixed(3) : "n/a"
      const content = clipText(memory?.content || memory?.content_preview || "", MAX_MEMORY_CHARS)
      return `${index + 1}. [${namespace}] score=${score}\n${content}`
    })
    .join("\n\n")
}

export default async function () {
  return {
    "chat.message": async (input, output) => {
      const query = extractPromptText(output)
      rememberSessionQuery(input?.sessionID, query)
    },

    "experimental.chat.system.transform": async (input, output) => {
      const sessionID = input?.sessionID
      const query = sessionID ? sessionQueries.get(sessionID)?.query : ""
      if (!query) return

      const recalled = await recallMemories(query, DEFAULT_LIMIT)
      if (!recalled.ok) return

      const block = formatMemoryBlock(recalled.data)
      if (!block) return

      output.system.push(block)
    },

    tool: {
      mnemlet_recall: tool({
        description: "Recall relevant memories from Mnémlet using its local REST API.",
        args: {
          query: tool.schema.string().describe("Search query for Mnémlet memory"),
          namespace: tool.schema.string().optional().describe("Optional Mnémlet namespace"),
          limit: tool.schema.number().int().min(1).max(10).default(DEFAULT_LIMIT).describe("Maximum memories to return"),
        },
        async execute(args) {
          const recalled = await recallMemories(args.query, args.limit || DEFAULT_LIMIT, args.namespace)
          if (!recalled.ok) return `Mnémlet recall failed: ${recalled.error}`
          return formatRecallToolOutput(recalled.data)
        },
      }),

      mnemlet_ingest: tool({
        description: "Store a memory in Mnémlet using its local REST API.",
        args: {
          content: tool.schema.string().describe("Memory content to store"),
          namespace: tool.schema.string().default("opencode/christoph/session").describe("Mnémlet namespace"),
          importance: tool.schema.number().min(0).max(1).default(0.5).describe("Memory importance from 0.0 to 1.0"),
        },
        async execute(args) {
          const stored = await postJson("/api/v1/ingest", {
            content: args.content,
            namespace: args.namespace || "opencode/christoph/session",
            importance: args.importance ?? 0.5,
          })
          if (!stored.ok) return `Mnémlet ingest failed: ${stored.error}`
          return JSON.stringify(stored.data, null, 2)
        },
      }),
    },
  }
}
```

- [ ] **Step 2: Syntax-check the plugin**

Run:

```bash
node --check '/home/christoph/.config/opencode/plugins/mnemlet-memory.js'
```

Expected: no output and exit code `0`.

- [ ] **Step 3: Verify OpenCode discovers the plugin**

Run:

```bash
opencode debug config
```

Expected: resolved config includes `file:///home/christoph/.config/opencode/plugins/mnemlet-memory.js` in the plugin list. If it does not, run Step 4.

- [ ] **Step 4: Add an explicit plugin entry only if auto-discovery did not list the plugin**

Run this exact command only if Step 3 did not show `mnemlet-memory.js`:

```bash
python - <<'PY'
from pathlib import Path
import json

config_path = Path('/home/christoph/.config/opencode/config.json')
data = json.loads(config_path.read_text(encoding='utf-8'))
plugins = data.setdefault('plugin', [])
for spec in [
    'file:///home/christoph/.config/opencode/plugins/claude-mem-observer.js',
    'file:///home/christoph/.config/opencode/plugins/mnemlet-memory.js',
]:
    if spec not in plugins:
        plugins.append(spec)
config_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
print('configured OpenCode plugin entries')
PY
```

Expected: prints `configured OpenCode plugin entries`.

- [ ] **Step 5: Verify plugin tools appear in OpenCode help context through a smoke run**

Run:

```bash
opencode run --print-logs --log-level INFO 'Use the mnemlet_recall tool to recall what you know about Mnémlet and OpenCode. Keep the answer short.'
```

Expected: OpenCode completes without plugin load errors. The response should mention Mnémlet/OpenCode memory if the model invokes the tool.

---

## Task 7: End-to-End Verification

**Files:**
- Reads runtime logs and local services.
- Does not modify source code.

- [ ] **Step 1: Seed a distinctive Mnémlet test memory**

Run:

```bash
curl -sS -X POST 'http://localhost:4050/api/v1/ingest' \
  -H 'Content-Type: application/json' \
  --data '{"content":"Integration sentinel: Christoph calls the Mnémlet OpenCode bridge Nebelkrähe.","namespace":"integration/sentinel","importance":0.95}'
```

Expected: JSON response contains `"stored":true`.

- [ ] **Step 2: Verify direct REST recall finds the sentinel**

Run:

```bash
curl -sS -X POST 'http://localhost:4050/api/v1/recall' \
  -H 'Content-Type: application/json' \
  --data '{"query":"What is the Mnémlet OpenCode bridge called?","limit":5,"min_score":0.1}'
```

Expected: JSON response contains `Nebelkrähe`.

- [ ] **Step 3: Verify OpenWebUI loader and inlet still inject context**

Run:

```bash
DATA_DIR='/home/christoph/mira/data' WEBUI_SECRET_KEY_FILE='/home/christoph/mira/.webui_secret_key' /home/christoph/mira/.venv/bin/python - <<'PY'
import asyncio
import sqlite3

from open_webui.utils.plugin import load_function_module_by_id

row = sqlite3.connect('/home/christoph/mira/data/webui.db').execute(
    "SELECT id, content FROM function WHERE name = ? AND type = ?",
    ('Mnémlet Memory', 'filter'),
).fetchone()
function_id, content = row


async def main() -> None:
    module, function_type, _ = await load_function_module_by_id(function_id, content)
    assert function_type == 'filter'
    body = {'messages': [{'role': 'user', 'content': 'What is the Mnémlet OpenCode bridge called?'}]}
    result = module.inlet(body)
    context = result['messages'][0]['content']
    assert 'Nebelkrähe' in context
    print(context)


asyncio.run(main())
PY
```

Expected: printed context contains `Nebelkrähe`.

- [ ] **Step 4: Verify OpenCode MCP list shows Mnémlet connected**

Run:

```bash
opencode mcp list
```

Expected: output includes `mnemlet` and `connected`.

- [ ] **Step 5: Verify an explicit Mnémlet MCP status tool call through OpenCode**

Run:

```bash
opencode run --print-logs --log-level INFO 'Use the mnemlet_status MCP tool and summarize the memory counts in one sentence.'
```

Expected: OpenCode completes without MCP errors, and the answer mentions memory counts or Mnémlet status fields.

- [ ] **Step 6: Verify OpenCode answers using Mnémlet context**

Run:

```bash
opencode run --print-logs --log-level INFO 'What is the Mnémlet OpenCode bridge called? Answer with only the codename.'
```

Expected: response contains `Nebelkrähe`.

- [ ] **Step 7: Verify OpenWebUI live chat manually without restarting it**

In the currently running OpenWebUI instance, send this message:

```text
What is the Mnémlet OpenCode bridge called? Answer with only the codename.
```

Expected: answer contains `Nebelkrähe`.

- [ ] **Step 8: Check OpenWebUI logs after the manual chat**

Run:

```bash
journalctl --user -u 'open-webui.service' --since '10 minutes ago' --grep='No Function class\|Error loading module\|Mnémlet inlet\|Mnémlet outlet' --no-pager
```

Expected: no `No Function class found` and no `Error loading module` lines for the Mnémlet function.

- [ ] **Step 9: Check Mnémlet logs after all integrations**

Run:

```bash
journalctl --user -u 'mnemlet.service' --since '10 minutes ago' --no-pager
```

Expected: shows successful `/api/v1/ingest`, `/api/v1/recall`, and MCP requests without `Task group is not initialized`.

- [ ] **Step 10: Final full Mnémlet tests**

Run:

```bash
/home/christoph/mnemlet/.venv/bin/python -m pytest -q
```

Expected: all tests pass.

---

## Rollback Commands

### Restore OpenWebUI function DB content from backup

Run this command to restore the newest DB-content backup created by Task 1 Step 5:

```bash
DATA_DIR='/home/christoph/mira/data' WEBUI_SECRET_KEY_FILE='/home/christoph/mira/.webui_secret_key' /home/christoph/mira/.venv/bin/python - <<'PY'
from pathlib import Path
import sqlite3
import time

backup_dir = Path('/home/christoph/mira/data/functions/backups')
backups = sorted(backup_dir.glob('mnemlet_function_db_content.*.py'))
if not backups:
    raise SystemExit('No mnemlet_function_db_content backup found')
backup_path = backups[-1]
content = backup_path.read_text(encoding='utf-8')
con = sqlite3.connect('/home/christoph/mira/data/webui.db')
con.execute(
    "UPDATE function SET content = ?, updated_at = ? WHERE name = ? AND type = ?",
    (content, int(time.time()), 'Mnémlet Memory', 'filter'),
)
con.commit()
print(f'restored OpenWebUI Mnémlet function content from {backup_path}')
PY
```

Expected: prints `restored OpenWebUI Mnémlet function content from` followed by a backup path.

### Disable the OpenWebUI Mnémlet filter without deleting it

Run:

```bash
DATA_DIR='/home/christoph/mira/data' WEBUI_SECRET_KEY_FILE='/home/christoph/mira/.webui_secret_key' /home/christoph/mira/.venv/bin/python - <<'PY'
import sqlite3
import time

con = sqlite3.connect('/home/christoph/mira/data/webui.db')
con.execute(
    "UPDATE function SET is_active = 0, updated_at = ? WHERE name = ? AND type = ?",
    (int(time.time()), 'Mnémlet Memory', 'filter'),
)
con.commit()
print('disabled Mnémlet Memory filter')
PY
```

Expected: prints `disabled Mnémlet Memory filter`.

### Remove Mnémlet from OpenCode config

Run:

```bash
python - <<'PY'
from pathlib import Path
import json

config_path = Path('/home/christoph/.config/opencode/config.json')
data = json.loads(config_path.read_text(encoding='utf-8'))
data.get('mcp', {}).pop('mnemlet', None)
plugins = data.get('plugin')
if isinstance(plugins, list):
    data['plugin'] = [p for p in plugins if p != 'file:///home/christoph/.config/opencode/plugins/mnemlet-memory.js']
config_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
print('removed Mnémlet OpenCode config')
PY
```

Expected: prints `removed Mnémlet OpenCode config`.

### Remove the OpenCode Mnémlet plugin

Run:

```bash
rm -f '/home/christoph/.config/opencode/plugins/mnemlet-memory.js'
```

Expected: no output and exit code `0`.

### Re-enable the duplicate system OpenWebUI service

Run only if Christoph explicitly wants the old system service back:

```bash
sudo systemctl unmask 'openwebui.service' && sudo systemctl enable 'openwebui.service'
```

Expected: systemd reports the unit is unmasked and enabled. Do not start it while the user service owns port `8080`.
