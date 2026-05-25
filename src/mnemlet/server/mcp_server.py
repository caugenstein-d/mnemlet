"""MCP (Model Context Protocol) server for Mnemlet — 14 tools."""

import json
from mcp.server.fastmcp import FastMCP

from mnemlet import __version__


def create_mcp_server(app_state) -> FastMCP:
    """Create an MCP server wired to the Mnemlet app state."""
    mcp = FastMCP("Mnemlet Memory Engine")
    mcp.settings.streamable_http_path = "/"

    @mcp.tool()
    async def mnemlet_ingest(
        content: str,
        namespace: str = "default",
        importance: float = 0.5,
    ) -> dict:
        """Store a new memory. Returns metadata about the stored memory."""
        engine = app_state.ingest_engine
        return engine.ingest(content=content, namespace=namespace, importance=importance)

    @mcp.tool()
    async def mnemlet_recall(
        query: str,
        namespace: str = None,
        limit: int = 5,
    ) -> dict:
        """Retrieve relevant memories for a query. Returns list of matching memories with scores."""
        engine = app_state.recall_engine
        results = engine.recall(query=query, namespace=namespace, limit=min(limit, 10))
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
        return build_context_pack(query, results, include_superseded=include_superseded)

    @mcp.tool()
    async def mnemlet_explain(memory_id: str) -> dict:
        """Explain provenance and lifecycle metadata for a memory."""
        from mnemlet.intelligence.provenance import explain_memory

        return explain_memory(app_state.db, memory_id)

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

        return ReviewService(app_state.db, app_state.ingest_engine).remember(content, namespace, importance, memory_type)

    @mcp.tool()
    async def mnemlet_forget(memory_id: str) -> dict:
        """Mark a memory as forgotten without deleting it."""
        from mnemlet.intelligence.review import ReviewService

        return ReviewService(app_state.db, app_state.ingest_engine).forget(memory_id)

    @mcp.tool()
    async def mnemlet_replace(memory_id: str, new_content: str, importance: float = 0.5) -> dict:
        """Replace a memory by superseding it and storing a new version."""
        from mnemlet.intelligence.review import ReviewService

        return ReviewService(app_state.db, app_state.ingest_engine).replace(memory_id, new_content, importance)

    @mcp.tool()
    async def mnemlet_confirm(memory_id: str) -> dict:
        """Confirm a memory and boost its retention score."""
        from mnemlet.intelligence.review import ReviewService

        return ReviewService(app_state.db, app_state.ingest_engine).confirm(memory_id)

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
        return {
            "active_memories": active,
            "cold_storage_memories": cold,
            "total_interactions": interactions,
            "chroma_documents": chroma.count(),
            "version": __version__,
        }

    @mcp.tool()
    async def mnemlet_namespaces(action: str = "list", namespace: str = None) -> dict:
        """Manage namespaces. action: 'list' to show all, 'create' to create one."""
        db = app_state.db
        if action == "list":
            rows = db.conn.execute(
                "SELECT DISTINCT namespace FROM memories "
                "UNION SELECT namespace FROM decay_configs"
            ).fetchall()
            return {"namespaces": [r[0] for r in rows]}
        elif action == "create" and namespace:
            db.set_decay_config(namespace)
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
        return db.get_memory(memory_id)

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
                return config
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
            return db.set_decay_config(namespace, **kwargs)
        return {"error": "invalid action. Use 'get' or 'set'."}

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
        return {
            "total_memories": count,
            "vault_path": vault_path,
            "export_note": (
                "Use GET /api/v1/vault for vault path, "
                "or mnemlet export CLI for full dump."
            ),
        }

    return mcp
