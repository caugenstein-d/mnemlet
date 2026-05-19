"""Sleep Engine — night consolidation during user inactivity."""

import time
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


class SleepEngine:
    """Orchestrates memory consolidation during user inactivity.

    Runs in a background thread. Triggers when no API calls for 2+ hours.
    Tasks run sequentially, never in parallel.
    """

    def __init__(self, db, chroma, embedder, vault, decay_engine=None,
                 inactivity_threshold_seconds: int = 7200):
        self.db = db
        self.chroma = chroma
        self.embedder = embedder
        self.vault = vault
        self.decay = decay_engine
        self.inactivity_threshold = inactivity_threshold_seconds
        self._last_activity = time.time()
        self._running = False
        self._paused = False
        self._thread = None
        self._checkpoint = {}  # task_name -> completed (bool)

    def bump_activity(self):
        """Call this on every API request to reset inactivity timer."""
        self._last_activity = time.time()

    @property
    def state(self) -> str:
        """Current sleep engine state."""
        if not self._running:
            return "idle"
        if self._paused:
            return "paused"
        return "running"

    @property
    def idle_seconds(self) -> float:
        """Seconds since last activity."""
        return time.time() - self._last_activity

    def should_sleep(self) -> bool:
        """Check if sleep phase should start."""
        return self.idle_seconds >= self.inactivity_threshold and not self._running

    def start(self, force: bool = False):
        """Start the sleep engine (non-blocking, runs in thread)."""
        if self._running and not force:
            return {"status": "already_running"}

        self._running = True
        self._paused = False
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        return {"status": "started"}

    def stop(self):
        """Gracefully stop the sleep engine."""
        self._running = False
        self._paused = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=30)
        return {"status": "stopped", "checkpoint": self._checkpoint}

    def _run_loop(self):
        """Main sleep loop — run consolidation tasks sequentially."""
        tasks = [
            self._task_dedup_today,
            self._task_rescore_stale,
            self._task_cluster_similar,
            self._task_prepare_briefing,
        ]

        for task in tasks:
            if not self._running:
                break
            task_name = task.__name__
            if self._checkpoint.get(task_name):
                continue  # Already completed, skip

            try:
                print(f"[sleep] Running: {task_name}")
                task()
                self._checkpoint[task_name] = True
            except Exception as e:
                print(f"[sleep] Task {task_name} failed: {e}")
                self._checkpoint[task_name] = False

            # Cooldown between tasks
            time.sleep(30)

        self._running = False
        print("[sleep] Consolidation complete")

    # --- Individual Sleep Tasks (deterministic mode) ---

    def _task_dedup_today(self):
        """Find and merge near-duplicate memories created today."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        rows = self.db.conn.execute(
            """SELECT id, content_preview, namespace FROM memories
               WHERE status = 'active' AND created_at >= ?
               ORDER BY created_at DESC LIMIT 200""",
            (today,),
        ).fetchall()

        seen = {}
        for row in rows:
            key = row["content_preview"][:80]
            ns = row["namespace"]
            if (ns, key) in seen:
                # Mark duplicate as cold_storage
                self.db.conn.execute(
                    "UPDATE memories SET status = 'cold_storage', retention_score = 0.02 WHERE id = ?",
                    (row["id"],),
                )
                print(f"[sleep] Dedup: moved {row['id'][:8]} to cold (dup of {seen[(ns,key)][:8]})")
            else:
                seen[(ns, key)] = row["id"]

        self.db.conn.commit()

    def _task_rescore_stale(self):
        """Apply decay to stale memories and run purge."""
        if self.decay:
            result = self.decay.decay_all_active(limit=500)
            print(f"[sleep] Rescore: processed {result['processed']}, "
                  f"decayed {result['decayed']}, "
                  f"cold={result['moved_to_cold']}, deleted={result['hard_deleted']}")

    def _task_cluster_similar(self):
        """Group semantically similar memories from today."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        rows = self.db.conn.execute(
            """SELECT id, content_preview, namespace, retention_score
               FROM memories WHERE status = 'active' AND created_at >= ?
               LIMIT 100""",
            (today,),
        ).fetchall()

        if len(rows) < 3:
            return

        # Simple clustering: group by content similarity via embedding
        # For deterministic mode: group by namespace
        from collections import Counter
        ns_counts = Counter(r["namespace"] for r in rows)
        for ns, count in ns_counts.most_common(5):
            print(f"[sleep] Cluster: namespace '{ns}' has {count} new memories today")

    def _task_prepare_briefing(self):
        """Generate a morning briefing from top-scored recent memories."""
        rows = self.db.conn.execute(
            """SELECT content_preview, namespace, retention_score
               FROM memories WHERE status = 'active'
               ORDER BY retention_score DESC LIMIT 10"""
        ).fetchall()

        if not rows:
            return

        lines = ["# Morning Briefing", "", f"Generated: {datetime.now(timezone.utc).isoformat()}", ""]
        for r in rows:
            lines.append(f"- [{r['namespace']}] (score: {r['retention_score']:.2f}) {r['content_preview'][:100]}")

        briefing = "\n".join(lines)

        # Store briefing as system memory
        now = datetime.now(timezone.utc).isoformat()
        import uuid
        bid = str(uuid.uuid4())[:8]
        self.db.conn.execute(
            """INSERT INTO memories (id, namespace, content_preview, retention_score,
               importance, created_at, last_accessed_at, status)
               VALUES (?, '__system__/morning_briefing', ?, 0.9, 0.8, ?, ?, 'active')""",
            (f"briefing-{bid}", briefing[:200], now, now),
        )
        self.db.conn.commit()

        # Also write to vault
        if self.vault:
            self.vault.write_memory(
                memory_id=f"briefing-{bid}",
                namespace="__system__/morning_briefing",
                content=briefing,
                retention_score=0.9,
                created_at=now,
            )

        print("[sleep] Morning briefing generated")
