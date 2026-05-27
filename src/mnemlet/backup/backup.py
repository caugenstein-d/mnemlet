"""Create portable Mnémlet backup archives."""

from __future__ import annotations

import io
import tarfile
from datetime import datetime, timezone
from pathlib import Path

from mnemlet.config import MnemletConfig


def create_backup(config: MnemletConfig, output_dir: Path | None = None) -> Path:
    """Create a timestamped tar.gz backup for the configured local data."""
    destination = output_dir or config.data_dir / "backups"
    destination.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = destination / f"mnemlet-backup-{timestamp}.tar.gz"

    with tarfile.open(backup_path, "w:gz") as tar:
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
