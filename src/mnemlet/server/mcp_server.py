"""MCP (Model Context Protocol) server for Mnemlet - 15 tools."""

import json
from typing import Any

from mcp.server.fastmcp import FastMCP

from mnemlet import __version__
from mnemlet.security.audit import AuditEvent, AuditResult
from mnemlet.security.secret_guard import SecretGuard


def create_mcp_server(app_state) -> FastMCP:
    """Create an MCP server wired to the Mnemlet app state."""
    mcp = FastMCP("Mnemlet Memory Engine")
    mcp.settings.streamable_http_path = "/"
    original_streamable_http_app = mcp.streamable_http_app

    def streamable_http_app_with_mcp_reference() -> Any:
        """Create the ASGI app and expose the FastMCP server for in-process tests."""
        mcp_app = original_streamable_http_app()
        if mcp._session_manager is not None:
            setattr(mcp._session_manager, "_mcp_server", mcp)
        return mcp_app

    mcp.streamable_http_app = streamable_http_app_with_mcp_reference

    def record_mcp_audit(
        action: str,
        namespace: str | None = None,
        memory_id: str | None = None,
        details: dict[str, Any] | None = None,
        result: AuditResult = "success",
    ) -> None:
        """Record sanitized MCP tool activity without request bodies or secrets."""
        app_state.db.record_audit(
            AuditEvent(
                action=action,
                namespace=namespace or "default",
                caller="mcp",
                memory_id=memory_id,
                result=result,
                details=details or {},
            )
        )

    def first_memory_id(result: dict[str, Any]) -> str | None:
        """Return the primary memory id from an MCP tool result."""
        memory_id = result.get("memory_id") or result.get("id")
        if isinstance(memory_id, list):
            return str(memory_id[0]) if memory_id else None
        return str(memory_id) if memory_id is not None else None

    def blocked_secret_details(exc: ValueError) -> dict[str, Any] | None:
        """Return sanitized secret guard details for blocked MCP writes."""
        message = str(exc)
        if not message.startswith("secret_guard_blocked: patterns="):
            return None
        patterns = message.rsplit("=", 1)[1]
        return {"secret_guard_patterns": [item for item in patterns.split(",") if item]}

    @mcp.tool()
    async def mnemlet_ingest(
        content: str,
        namespace: str = "default",
        importance: float = 0.5,
    ) -> dict:
        """Store a new memory. Returns metadata about the stored memory."""
        engine = app_state.ingest_engine
        try:
            result = engine.ingest(content=content, namespace=namespace, importance=importance, caller="mcp")
        except ValueError as exc:
            details = blocked_secret_details(exc)
            if details is not None:
                record_mcp_audit("ingest", namespace=namespace, details=details, result="blocked")
            raise
        record_mcp_audit("ingest", namespace=namespace, memory_id=first_memory_id(result))
        return result

    @mcp.tool()
    async def mnemlet_recall(
        query: str,
        namespace: str = None,
        limit: int = 5,
    ) -> dict:
        """Retrieve relevant memories for a query. Returns list of matching memories with scores."""
        engine = app_state.recall_engine
        results = engine.recall(query=query, namespace=namespace, limit=min(limit, 10))
        record_mcp_audit("recall", namespace=namespace, details={"count": len(results)})
        return {"results": results, "count": len(results)}

    @mcp.tool()
    async def mnemlet_context(
        query: str,
        namespace: str = None,
        limit: int = 5,
        min_score: float = 0.0,
        include_superseded: bool = False,
    ) -> dict:
        """Retrieve an agent-friendly Context Pack with abstention metadata."""
        from mnemlet.intelligence.context_pack import build_context_pack
        from mnemlet.intelligence.policy import recall_statuses

        engine = app_state.recall_engine
        results = engine.recall(
            query=query,
            namespace=namespace,
            limit=min(limit, 10),
            min_score=min_score,
            include_statuses=recall_statuses(include_superseded=include_superseded),
        )
        record_mcp_audit("context", namespace=namespace, details={"count": len(results)})
        return build_context_pack(query, results, include_superseded=include_superseded)

    @mcp.tool()
    async def mnemlet_explain(memory_id: str) -> dict:
        """Explain provenance and lifecycle metadata for a memory."""
        from mnemlet.intelligence.provenance import explain_memory

        result = explain_memory(app_state.db, memory_id)
        record_mcp_audit("explain", namespace=result.get("namespace"), memory_id=memory_id)
        return result

    @mcp.tool()
    async def mnemlet_remember(
        content: str,
        namespace: str = "default",
        importance: float = 0.5,
        memory_type: str = None,
    ) -> dict:
        """Deliberately store a memory, optionally with explicit type."""
        if memory_type is not None:
            from mnemlet.constants import MEMORY_TYPES
            if memory_type not in MEMORY_TYPES:
                raise ValueError(f"invalid memory type: {memory_type}")
        from mnemlet.intelligence.review import ReviewService

        try:
            result = ReviewService(app_state.db, app_state.ingest_engine).remember(content, namespace, importance, memory_type)
        except ValueError as exc:
            details = blocked_secret_details(exc)
            if details is not None:
                record_mcp_audit("ingest", namespace=namespace, details=details, result="blocked")
            raise
        record_mcp_audit("ingest", namespace=namespace, memory_id=first_memory_id(result))
        return result

    @mcp.tool()
    async def mnemlet_forget(memory_id: str) -> dict:
        """Mark a memory as forgotten without deleting it."""
        from mnemlet.intelligence.review import ReviewService

        result = ReviewService(app_state.db, app_state.ingest_engine).forget(memory_id)
        record_mcp_audit("forget", namespace=result.get("namespace"), memory_id=memory_id)
        return result

    @mcp.tool()
    async def mnemlet_replace(memory_id: str, new_content: str, importance: float = 0.5) -> dict:
        """Replace a memory by superseding it and storing a new version."""
        from mnemlet.intelligence.review import ReviewService

        try:
            result = ReviewService(app_state.db, app_state.ingest_engine).replace(memory_id, new_content, importance)
        except ValueError as exc:
            details = blocked_secret_details(exc)
            if details is not None:
                record_mcp_audit("replace", memory_id=memory_id, details=details, result="blocked")
            raise
        record_mcp_audit("replace", namespace=result.get("namespace"), memory_id=memory_id)
        return result

    @mcp.tool()
    async def mnemlet_confirm(memory_id: str) -> dict:
        """Confirm a memory and boost its retention score."""
        from mnemlet.intelligence.review import ReviewService

        result = ReviewService(app_state.db, app_state.ingest_engine).confirm(memory_id)
        record_mcp_audit("confirm", namespace=result.get("namespace"), memory_id=memory_id)
        return result

    @mcp.tool()
    async def mnemlet_search(
        query: str,
        namespaces: str = None,
        limit: int = 5,
    ) -> dict:
        """Search across multiple namespaces (comma-separated). Returns matching memories."""
        engine = app_state.recall_engine
        if namespaces:
            ns_list = [ns.strip() for ns in namespaces.split(",") if ns.strip()]
            all_results = []
            seen_ids = set()
            cap = min(limit, 10)
            for ns in ns_list:
                ns_results = engine.recall(query=query, namespace=ns, limit=cap)
                for r in ns_results:
                    if r["id"] not in seen_ids:
                        seen_ids.add(r["id"])
                        all_results.append(r)
            all_results.sort(key=lambda x: x["score"], reverse=True)
            all_results = all_results[:cap]
        else:
            all_results = engine.recall(query=query, limit=min(limit, 10))
        record_mcp_audit("search", namespace="default", details={"count": len(all_results)})
        return {"results": all_results, "count": len(all_results)}

    @mcp.tool()
    async def mnemlet_status() -> dict:
        """Get system status: memory counts, storage info, decay stats."""
        db = app_state.db
        chroma = app_state.chroma
        active = db.conn.execute(
            "SELECT COUNT(*) FROM memories WHERE status = 'active'"
        ).fetchone()[0]
        cold = db.conn.execute(
            "SELECT COUNT(*) FROM memories WHERE status = 'cold_storage'"
        ).fetchone()[0]
        interactions = db.conn.execute(
            "SELECT COUNT(*) FROM interactions"
        ).fetchone()[0]
        result = {
            "active_memories": active,
            "cold_storage_memories": cold,
            "total_interactions": interactions,
            "chroma_documents": chroma.count(),
            "version": __version__,
        }
        record_mcp_audit("status")
        return result

    @mcp.tool()
    async def mnemlet_namespaces(action: str = "list", namespace: str = None) -> dict:
        """Manage namespaces. action: 'list' to show all, 'create' to create one."""
        db = app_state.db
        if action == "list":
            rows = db.conn.execute(
                "SELECT DISTINCT namespace FROM memories "
                "UNION SELECT namespace FROM decay_configs"
            ).fetchall()
            record_mcp_audit("namespaces", details={"action": "list"})
            return {"namespaces": [r[0] for r in rows]}
        elif action == "create" and namespace:
            db.set_decay_config(namespace)
            record_mcp_audit("namespaces", namespace=namespace, details={"action": "create"})
            return {
                "created": namespace,
                "note": "namespace will be active on first ingest",
            }
        return {
            "error": "invalid action. Use 'list' or 'create' with namespace parameter."
        }

    @mcp.tool()
    async def mnemlet_update(
        memory_id: str,
        content: str = None,
        importance: float = None,
        status: str = None,
    ) -> dict:
        """Update or delete a memory. Set status='deleted' to remove."""
        db = app_state.db
        memory = db.get_memory(memory_id)
        if not memory:
            return {"error": f"Memory {memory_id} not found"}

        if content:
            guard_result = SecretGuard().enforce(content, "block")
            if guard_result.blocked:
                patterns = sorted({finding.pattern_type for finding in guard_result.findings})
                message = f"secret_guard_blocked: patterns={','.join(patterns)}"
                record_mcp_audit(
                    "update",
                    namespace=memory.get("namespace"),
                    memory_id=memory_id,
                    details={"secret_guard_patterns": patterns},
                    result="blocked",
                )
                raise ValueError(message)
            db.conn.execute(
                "UPDATE memories SET content_preview = ?, "
                "metadata_json = json_set(metadata_json, '$.updated', 'true') "
                "WHERE id = ?",
                (content[:200], memory_id),
            )
        if importance is not None:
            db.conn.execute(
                "UPDATE memories SET importance = ?, retention_score = ? WHERE id = ?",
                (importance, importance * 0.5, memory_id),
            )
        if status:
            db.conn.execute(
                "UPDATE memories SET status = ? WHERE id = ?",
                (status, memory_id),
            )

        db.conn.commit()
        result = db.get_memory(memory_id)
        record_mcp_audit("update", namespace=result.get("namespace"), memory_id=memory_id)
        return result

    @mcp.tool()
    async def mnemlet_decay_config(
        namespace: str,
        action: str = "get",
        lambda_: float = None,
        purge_threshold: float = None,
    ) -> dict:
        """Get or set decay configuration for a namespace. action: 'get' or 'set'."""
        db = app_state.db
        if action == "get":
            config = db.get_decay_config(namespace)
            if config:
                record_mcp_audit("decay_config", namespace=namespace, details={"action": "get"})
                return config
            record_mcp_audit("decay_config", namespace=namespace, details={"action": "get"})
            return {
                "namespace": namespace,
                "note": "using defaults",
                "lambda": 0.01,
                "purge_threshold": 0.05,
            }
        elif action == "set":
            kwargs = {}
            if lambda_ is not None:
                kwargs["lambda_"] = lambda_
            if purge_threshold is not None:
                kwargs["purge_threshold"] = purge_threshold
            result = db.set_decay_config(namespace, **kwargs)
            record_mcp_audit("decay_config", namespace=namespace, details={"action": "set"})
            return result
        return {"error": "invalid action. Use 'get' or 'set'."}

    @mcp.tool()
    async def mnemlet_audit(
        namespace: str = None,
        action: str = None,
        since: str = None,
        limit: int = 100,
    ) -> dict:
        """Read recent audit log events."""
        events = app_state.db.query_audit(
            namespace=namespace,
            action=action,
            since=since,
            limit=min(limit, 500),
        )
        record_mcp_audit("audit", namespace=namespace, details={"count": len(events)})
        return {"events": events, "count": len(events)}

    @mcp.tool()
    async def mnemlet_export(format: str = "json") -> dict:
        """Export memory statistics and vault location."""
        db = app_state.db
        vault_path = (
            str(app_state.config.vault_path)
            if hasattr(app_state, "config")
            else "~/.mnemlet/vault"
        )
        count = db.conn.execute(
            "SELECT COUNT(*) FROM memories"
        ).fetchone()[0]
        result = {
            "total_memories": count,
            "vault_path": vault_path,
            "export_note": (
                "Use GET /api/v1/vault for vault path, "
                "or mnemlet export CLI for full dump."
            ),
        }
        record_mcp_audit("export", details={"format": format})
        return result

    return mcp
