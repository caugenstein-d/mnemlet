"""Create portable Mnémlet backup archives."""

from __future__ import annotations

import io
import tarfile
from datetime import datetime, timezone
from pathlib import Path

from mnemlet.config import MnemletConfig
from mnemlet.storage.sqlite import MnemletDB


def create_backup(config: MnemletConfig, output_dir: Path | None = None) -> Path:
    """Create a timestamped tar.gz backup for the configured local data."""
    _ensure_sqlite_db(config.sqlite_path)
    destination = output_dir or config.data_dir / "backups"
    destination.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup_path, backup_file = _open_unique_backup(destination, timestamp)

    with backup_file:
        with tarfile.open(fileobj=backup_file, mode="w:gz") as tar:
            if config.sqlite_path.exists():
                tar.add(config.sqlite_path, arcname="mnemlet.db")
            for suffix in ("-wal", "-shm"):
                sidecar = Path(f"{config.sqlite_path}{suffix}")
                if sidecar.exists():
                    tar.add(sidecar, arcname=f"mnemlet.db{suffix}")
            if config.vault_path.exists():
                tar.add(config.vault_path, arcname="vault")
            if config.chroma_path.exists():
                tar.add(config.chroma_path, arcname="chroma")

            config_text = _redacted_config(config).encode("utf-8")
            info = tarfile.TarInfo("config.toml")
            info.size = len(config_text)
            info.mtime = int(datetime.now(timezone.utc).timestamp())
            tar.addfile(info, io.BytesIO(config_text))

    return backup_path


def _ensure_sqlite_db(sqlite_path: Path) -> None:
    """Create an empty SQLite database when backing up a fresh data directory."""
    if sqlite_path.exists():
        return
    db = MnemletDB(sqlite_path)
    db.close()


def _open_unique_backup(destination: Path, timestamp: str) -> tuple[Path, io.BufferedWriter]:
    """Open a collision-resistant backup path without overwriting an existing archive."""
    for attempt in range(100):
        suffix = "" if attempt == 0 else f"-{attempt}"
        backup_path = destination / f"mnemlet-backup-{timestamp}{suffix}.tar.gz"
        try:
            return backup_path, backup_path.open("xb")
        except FileExistsError:
            continue
    raise RuntimeError("Unable to create a unique backup archive path")


def _redacted_config(config: MnemletConfig) -> str:
    """Render non-secret configuration metadata for a backup archive."""
    return "\n".join(
        [
            "[storage]",
            f'data_dir = "{config.data_dir}"',
            f'sqlite_path = "{config.sqlite_path}"',
            f'chroma_path = "{config.chroma_path}"',
            f'vault_path = "{config.vault_path}"',
            "",
            "[embedding]",
            f'model = "{config.embedding_model}"',
            f'cache_dir = "{config.embedding_cache_dir}"',
            "",
            "[auth]",
            'api_key = "<redacted>"',
            "",
        ]
    )
