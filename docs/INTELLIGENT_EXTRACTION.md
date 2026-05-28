# Intelligent Memory Extraction (v0.4)

## Overview

Mnémlet v0.4 adds **automatic memory extraction from conversations**. Instead of
only storing raw chat messages verbatim, Mnémlet can now:

1. **Buffer conversations** — collect messages per session and detect session
   boundaries (default: 10 minutes of inactivity)
2. **Extract individual memories** — preferences, facts, decisions, and context
3. **Summarize conversations** — condense an entire discussion into one memory
4. **Generate intelligent briefings** — morning briefings written by the LLM
   instead of a flat list of top memories

It is **opt-in** and **off by default**. With no LLM configured, Mnémlet behaves
exactly as in v0.3 (verbatim ingest, naive briefing). When you enable an LLM and
extraction, the new pipeline activates.

## How It Works

```
messages → adapter → conversation buffer → (extractor + summarizer) → ingest
```

### Platform Adapters

Each platform has an adapter that normalizes its chat format into a unified
`Conversation`. Phase 1 (v0.4 core) ships adapters for:

- OpenWebUI
- Claude Code
- OpenCode
- OpenClaw
- Cursor
- Claude Desktop
- Generic MCP clients (permissive fallback)

Unknown platforms fall back to the generic adapter. (Phase 2 adds Windsurf,
VS Code + Copilot, and Cline; Phase 3 adds Zed, Continue.dev, and LibreChat.)

### Conversation Buffer

Messages are buffered per session. A session ends — and is processed — when:

- No new messages arrive for `inactivity_threshold_minutes` (default 10), **or**
- The buffer reaches `max_messages` (default 100), **or**
- The pipeline is explicitly flushed.

The inactivity timer is a daemon thread, so it never blocks process exit. On
server shutdown the buffer is dropped without a (potentially slow) LLM flush.

### Memory Extraction & Summarization

When a session completes and an LLM is configured, Mnémlet:

1. **Extracts individual memories** — the LLM returns a JSON array of
   `{content, type, importance, namespace}`. Importance is clamped to `[0, 1]`,
   blank/invalid entries are dropped.
2. **Summarizes the conversation** — one concise summary memory (importance 0.7).

Each extracted memory is stored through the normal ingest pipeline (Secret Guard,
decay, vault write all apply) and tagged with provenance metadata
(`source=extraction_pipeline`, `platform`, `session_id`). A single failing
memory never aborts the rest of the session.

### Morning Briefings

The Sleep Engine's briefing task now uses the LLM (when present) to produce a
structured briefing — **Current Projects**, **Key Preferences**, **Recent
Activity**, **Today's Focus** — and falls back to the naive top-memory list if no
LLM is configured, the model errors, or it returns nothing.

## Feeding Conversations: `mnemlet_observe`

`mnemlet_ingest` is unchanged — it still stores content immediately and verbatim.
v0.4 adds a separate MCP tool, **`mnemlet_observe`**, for passive conversation
capture:

```jsonc
// mnemlet_observe arguments
{
  "content": "I prefer dark mode in all editors",
  "role": "user",            // user | assistant | system
  "session_id": "chat-123",  // groups messages into a session
  "namespace": "preferences",
  "platform": "openwebui"
}
```

- When extraction is **enabled**, the message is buffered and processed when the
  session ends: `{"buffered": true, "session_id": "chat-123", ...}`.
- When extraction is **disabled**, it returns a hint to use `mnemlet_ingest`
  instead: `{"buffered": false, "note": "..."}`.

## Configuration

Enable an LLM backend and the extraction pipeline in `mnemlet.toml`:

```toml
[llm]
enabled = true
provider = "ollama"
model = "gemma3:4b"
base_url = "http://localhost:11434"
temperature = 0.3
max_tokens = 4096

[intelligence]
extraction_enabled = true
extract_memories = true
summarize_conversations = true
inactivity_threshold_minutes = 10
max_messages = 100
```

Environment overrides for quick toggling:

- `MNEMLET_LLM_ENABLED=1`
- `MNEMLET_EXTRACTION_ENABLED=1`
- `MNEMLET_LLM_MODEL`, `MNEMLET_LLM_BASE_URL`

Notes:

- Extraction requires `[llm].enabled = true`. Enabling the LLM **without**
  extraction still upgrades the morning briefing.
- The LLM runs locally (Ollama or any OpenAI-compatible endpoint); no cloud
  calls and no API costs.

## Requirements

- An LLM endpoint (Ollama recommended; runs CPU-only on a Pi)
- Python 3.12+

## Example

**Before (v0.3, verbatim):**

```
User: I prefer dark mode
Assistant: Got it!
```

Stored as: `"I prefer dark mode"` (raw message).

**After (v0.4, extracted):**

Stored as: `"Christoph prefers dark mode in all editors"`
(type: preference, importance: 0.9) — plus a one-line conversation summary.
