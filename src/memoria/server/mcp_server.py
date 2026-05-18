"""MCP (Model Context Protocol) server for Memoria — 8 tools."""

import json
from mcp.server.fastmcp import FastMCP


def create_mcp_server(app_state) -> FastMCP:
    """Create an MCP server wired to the Memoria app state."""
    mcp = FastMCP("Memoria Memory Engine")
    mcp.settings.streamable_http_path = "/"

    @mcp.tool()
    async def memoria_ingest(
        content: str,
        namespace: str = "default",
        importance: float = 0.5,
    ) -> dict:
        """Store a new memory. Returns metadata about the stored memory."""
        engine = app_state.ingest_engine
        return engine.ingest(content=content, namespace=namespace, importance=importance)

    @mcp.tool()
    async def memoria_recall(
        query: str,
        namespace: str = None,
        limit: int = 5,
    ) -> dict:
        """Retrieve relevant memories for a query. Returns list of matching memories with scores."""
        engine = app_state.recall_engine
        results = engine.recall(query=query, namespace=namespace, limit=min(limit, 10))
        return {"results": results, "count": len(results)}

    @mcp.tool()
    async def memoria_search(
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
    async def memoria_status() -> dict:
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
            "version": "0.1.0",
        }

    @mcp.tool()
    async def memoria_namespaces(action: str = "list", namespace: str = None) -> dict:
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
    async def memoria_update(
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
    async def memoria_decay_config(
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
    async def memoria_export(format: str = "json") -> dict:
        """Export memory statistics and vault location."""
        db = app_state.db
        vault_path = (
            str(app_state.config.vault_path)
            if hasattr(app_state, "config")
            else "~/.memoria/vault"
        )
        count = db.conn.execute(
            "SELECT COUNT(*) FROM memories"
        ).fetchone()[0]
        return {
            "total_memories": count,
            "vault_path": vault_path,
            "export_note": (
                "Use GET /api/v1/vault for vault path, "
                "or memoria export CLI for full dump."
            ),
        }

    return mcp
