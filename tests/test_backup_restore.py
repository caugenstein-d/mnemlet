"""Tests for v0.3 backup and restore."""

from __future__ import annotations

import tarfile
from pathlib import Path

from mnemlet.backup.backup import create_backup
from mnemlet.backup.restore import restore_backup
from mnemlet.config import MnemletConfig
from mnemlet.storage.sqlite import MnemletDB


def _config(base: Path, *, api_key: str | None = None) -> MnemletConfig:
    return MnemletConfig(
        data_dir=base,
        sqlite_path=base / "mnemlet.db",
        chroma_path=base / "chroma",
        vault_path=base / "vault",
        embedding_cache_dir=base / "models",
        api_key=api_key,
    )


def test_backup_creates_tarball_without_api_key(tmp_path: Path) -> None:
    config = _config(tmp_path / "data", api_key="mnemlet_secret_1234567890abcdef")
    db = MnemletDB(config.sqlite_path)
    db.insert_memory(namespace="preferences", content_preview="dark mode")
    db.close()
    (config.vault_path / "preferences" / "2026-05").mkdir(parents=True)
    (config.vault_path / "preferences" / "2026-05" / "abc.md").write_text("memory")

    backup_path = create_backup(config, output_dir=tmp_path / "backups")

    assert backup_path.exists()
    with tarfile.open(backup_path, "r:gz") as tar:
        names = tar.getnames()
        content = "\n".join(names)
    assert "mnemlet.db" in content
    assert "vault" in content
    assert "mnemlet_secret" not in backup_path.read_bytes().decode("latin1", errors="ignore")


def test_restore_replaces_data_and_creates_pre_restore_backup(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source_config = _config(source)
    target_config = _config(target)

    db = MnemletDB(source_config.sqlite_path)
    original = db.insert_memory(namespace="preferences", content_preview="original")
    db.close()
    backup_path = create_backup(source_config, output_dir=tmp_path / "backups")

    target_db = MnemletDB(target_config.sqlite_path)
    target_db.insert_memory(namespace="preferences", content_preview="changed")
    target_db.close()

    result = restore_backup(target_config, backup_path, confirm=True)

    restored_db = MnemletDB(target_config.sqlite_path)
    try:
        restored = restored_db.get_memory(original["id"])
    finally:
        restored_db.close()
    assert restored is not None
    assert Path(result["pre_restore_backup"]).exists()
