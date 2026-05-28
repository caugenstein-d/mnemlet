"""Markdown vault writer — inspectable memory storage."""

import os
from datetime import datetime
from pathlib import Path
from typing import Optional


class VaultWriter:
    """Writes memories as inspectable Markdown files."""

    def __init__(self, vault_path: Path):
        self.vault_path = vault_path
        vault_path.mkdir(parents=True, exist_ok=True)

    def write_memory(self, memory_id: str, namespace: str, content: str,
                     retention_score: float = 0.5, importance: float = 0.5,
                     created_at: str = "", last_accessed_at: str = "",
                     access_count: int = 0, metadata: Optional[dict] = None) -> Path:
        """Write a memory as a Markdown file in the vault.

        Returns the file path.
        """
        # Build path: vault/{namespace}/{YYYY-MM}/{id}.md
        now = datetime.now()
        month_dir = now.strftime("%Y-%m")
        ns_dir = self.vault_path / namespace / month_dir
        ns_dir.mkdir(parents=True, exist_ok=True)

        file_path = ns_dir / f"{memory_id}.md"

        # Build frontmatter
        frontmatter = f"""---
id: {memory_id}
namespace: {namespace}
retention_score: {retention_score}
importance: {importance}
created: {created_at or now.isoformat()}
last_accessed: {last_accessed_at or now.isoformat()}
access_count: {access_count}
"""

        if metadata:
            for key, value in metadata.items():
                frontmatter += f"{key}: {value}\n"

        frontmatter += "---\n\n"

        # Write file
        with open(file_path, "w") as f:
            f.write(frontmatter)
            f.write(content)

        return file_path

    def find_memory_file(self, namespace: str, memory_id: str) -> Optional[Path]:
        """Return the vault file path for a memory, searching all month dirs."""
        ns_dir = self.vault_path / namespace
        if not ns_dir.exists():
            return None

        for month_dir in sorted(ns_dir.iterdir(), reverse=True):
            if not month_dir.is_dir():
                continue
            file_path = month_dir / f"{memory_id}.md"
            if file_path.exists():
                return file_path

        return None

    def read_memory(self, namespace: str, memory_id: str) -> Optional[str]:
        """Read a memory from the vault. Searches all month dirs."""
        file_path = self.find_memory_file(namespace, memory_id)
        return file_path.read_text() if file_path else None

    def list_memories(self, namespace: str, limit: int = 100) -> list[Path]:
        """List memory files for a namespace."""
        ns_dir = self.vault_path / namespace
        if not ns_dir.exists():
            return []

        files = []
        for month_dir in sorted(ns_dir.iterdir(), reverse=True):
            for f in sorted(month_dir.glob("*.md"), reverse=True):
                files.append(f)
                if len(files) >= limit:
                    return files
        return files
