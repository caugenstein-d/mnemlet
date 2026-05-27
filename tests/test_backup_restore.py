"""Tests for v0.3 backup and restore."""

from __future__ import annotations

import io
import os
import sqlite3
import subprocess
import tarfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

import mnemlet.backup.backup as backup_module
import mnemlet.backup.restore as restore_module
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


def test_restore_rejects_archive_without_db_and_preserves_current_db(tmp_path: Path) -> None:
    target_config = _config(tmp_path / "target")
    target_db = MnemletDB(target_config.sqlite_path)
    current = target_db.insert_memory(namespace="preferences", content_preview="current")
    target_db.close()
    backup_path = tmp_path / "missing-db.tar.gz"
    with tarfile.open(backup_path, "w:gz") as tar:
        config_text = b"[auth]\napi_key = \"<redacted>\"\n"
        info = tarfile.TarInfo("config.toml")
        info.size = len(config_text)
        tar.addfile(info, fileobj=io.BytesIO(config_text))

    with pytest.raises(ValueError, match="mnemlet.db"):
        restore_backup(target_config, backup_path, confirm=True)

    restored_db = MnemletDB(target_config.sqlite_path)
    try:
        assert restored_db.get_memory(current["id"]) is not None
    finally:
        restored_db.close()


def test_restore_rejects_malformed_sqlite_db_and_preserves_current_data(tmp_path: Path) -> None:
    target_config = _config(tmp_path / "target")
    target_db = MnemletDB(target_config.sqlite_path)
    current = target_db.insert_memory(namespace="preferences", content_preview="current")
    target_db.close()
    target_config.vault_path.mkdir(parents=True)
    keep_file = target_config.vault_path / "keep.md"
    keep_file.write_text("keep")
    backup_path = tmp_path / "malformed-db.tar.gz"
    with tarfile.open(backup_path, "w:gz") as tar:
        bad_db = b"not a sqlite database"
        info = tarfile.TarInfo("mnemlet.db")
        info.size = len(bad_db)
        tar.addfile(info, fileobj=io.BytesIO(bad_db))
        config_text = b"[auth]\napi_key = \"<redacted>\"\n"
        config_info = tarfile.TarInfo("config.toml")
        config_info.size = len(config_text)
        tar.addfile(config_info, fileobj=io.BytesIO(config_text))

    with pytest.raises(ValueError, match="SQLite"):
        restore_backup(target_config, backup_path, confirm=True)

    preserved_db = MnemletDB(target_config.sqlite_path)
    try:
        assert preserved_db.get_memory(current["id"]) is not None
    finally:
        preserved_db.close()
    assert keep_file.read_text() == "keep"


def test_restore_validates_sqlite_with_wal_sidecar(tmp_path: Path) -> None:
    source_db_path = tmp_path / "wal-source" / "mnemlet.db"
    source_db_path.parent.mkdir()
    conn = sqlite3.connect(source_db_path)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA wal_autocheckpoint=0")
        conn.execute("CREATE TABLE memories (id TEXT PRIMARY KEY, content_preview TEXT NOT NULL)")
        conn.execute("INSERT INTO memories (id, content_preview) VALUES ('wal-only', 'from wal')")
        conn.commit()
        backup_path = tmp_path / "wal-backup.tar.gz"
        with tarfile.open(backup_path, "w:gz") as tar:
            tar.add(source_db_path, arcname="mnemlet.db")
            tar.add(Path(f"{source_db_path}-wal"), arcname="mnemlet.db-wal")
            tar.add(Path(f"{source_db_path}-shm"), arcname="mnemlet.db-shm")
    finally:
        conn.close()

    target_config = _config(tmp_path / "target")
    restore_backup(target_config, backup_path, confirm=True)

    restored = sqlite3.connect(target_config.sqlite_path)
    try:
        row = restored.execute("SELECT content_preview FROM memories WHERE id = 'wal-only'").fetchone()
    finally:
        restored.close()
    assert row == ("from wal",)


def test_restore_rejects_file_vault_and_preserves_current_vault(tmp_path: Path) -> None:
    source_config = _config(tmp_path / "source")
    target_config = _config(tmp_path / "target")
    source_db = MnemletDB(source_config.sqlite_path)
    source_db.insert_memory(namespace="preferences", content_preview="source")
    source_db.close()
    target_config.vault_path.mkdir(parents=True)
    existing_file = target_config.vault_path / "existing.md"
    existing_file.write_text("keep me")
    backup_path = tmp_path / "file-vault.tar.gz"

    with tarfile.open(backup_path, "w:gz") as tar:
        tar.add(source_config.sqlite_path, arcname="mnemlet.db")
        vault_content = b"not a directory"
        info = tarfile.TarInfo("vault")
        info.size = len(vault_content)
        tar.addfile(info, fileobj=io.BytesIO(vault_content))

    with pytest.raises(ValueError, match="vault"):
        restore_backup(target_config, backup_path, confirm=True)

    assert existing_file.read_text() == "keep me"


def test_backup_paths_are_unique_within_same_second(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = _config(tmp_path / "data")
    db = MnemletDB(config.sqlite_path)
    db.insert_memory(namespace="preferences", content_preview="dark mode")
    db.close()

    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz: timezone | None = None) -> datetime:
            return cls(2026, 5, 27, 14, 0, 0, tzinfo=tz)

    monkeypatch.setattr(backup_module, "datetime", FixedDatetime)

    first = create_backup(config, output_dir=tmp_path / "backups")
    second = create_backup(config, output_dir=tmp_path / "backups")

    assert first != second
    assert first.exists()
    assert second.exists()


def test_restore_refuses_non_empty_target_without_confirm_and_preserves_db(tmp_path: Path) -> None:
    source_config = _config(tmp_path / "source")
    target_config = _config(tmp_path / "target")
    source_db = MnemletDB(source_config.sqlite_path)
    source_db.insert_memory(namespace="preferences", content_preview="source")
    source_db.close()
    backup_path = create_backup(source_config, output_dir=tmp_path / "backups")
    target_db = MnemletDB(target_config.sqlite_path)
    current = target_db.insert_memory(namespace="preferences", content_preview="current")
    target_db.close()

    with pytest.raises(RuntimeError, match="non-empty"):
        restore_backup(target_config, backup_path)

    preserved_db = MnemletDB(target_config.sqlite_path)
    try:
        assert preserved_db.get_memory(current["id"]) is not None
    finally:
        preserved_db.close()


def test_backup_and_restore_sidecar_files(tmp_path: Path) -> None:
    source_config = _config(tmp_path / "source")
    target_config = _config(tmp_path / "target")
    source_db = MnemletDB(source_config.sqlite_path)
    source_db.insert_memory(namespace="preferences", content_preview="source")
    source_db.close()
    source_wal = Path(f"{source_config.sqlite_path}-wal")
    source_shm = Path(f"{source_config.sqlite_path}-shm")
    source_wal.write_text("source wal")
    source_shm.write_text("source shm")
    target_db = MnemletDB(target_config.sqlite_path)
    target_db.insert_memory(namespace="preferences", content_preview="target")
    target_db.close()
    target_wal = Path(f"{target_config.sqlite_path}-wal")
    target_shm = Path(f"{target_config.sqlite_path}-shm")
    target_wal.write_text("target wal")
    target_shm.write_text("target shm")

    backup_path = create_backup(source_config, output_dir=tmp_path / "backups")

    with tarfile.open(backup_path, "r:gz") as tar:
        names = tar.getnames()
    assert "mnemlet.db-wal" in names
    assert "mnemlet.db-shm" in names

    restore_backup(target_config, backup_path, confirm=True)

    assert target_wal.read_text() == "source wal"
    assert target_shm.read_text() == "source shm"


def test_restore_removes_stale_sidecars_absent_from_backup(tmp_path: Path) -> None:
    source_config = _config(tmp_path / "source")
    target_config = _config(tmp_path / "target")
    source_db = MnemletDB(source_config.sqlite_path)
    source_db.insert_memory(namespace="preferences", content_preview="source")
    source_db.close()
    target_db = MnemletDB(target_config.sqlite_path)
    target_db.insert_memory(namespace="preferences", content_preview="target")
    target_db.close()
    target_wal = Path(f"{target_config.sqlite_path}-wal")
    target_shm = Path(f"{target_config.sqlite_path}-shm")
    target_wal.write_text("stale wal")
    target_shm.write_text("stale shm")
    backup_path = create_backup(source_config, output_dir=tmp_path / "backups")

    restore_backup(target_config, backup_path, confirm=True)

    assert not target_wal.exists()
    assert not target_shm.exists()


def test_cli_backup_prints_archive_under_requested_output(tmp_path: Path) -> None:
    output_dir = tmp_path / "backups"
    env = {**os.environ, "MNEMLET_DATA_DIR": str(tmp_path / "data")}

    result = subprocess.run(
        [".venv/bin/mnemlet", "backup", "--output", str(output_dir)],
        check=True,
        cwd=Path(__file__).parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    printed_path = Path(result.stdout.strip().removeprefix("Backup created: "))
    assert printed_path.suffixes[-2:] == [".tar", ".gz"]
    assert printed_path.parent == output_dir
    assert printed_path.exists()


def test_cli_backup_from_empty_data_dir_includes_restorable_db(tmp_path: Path) -> None:
    output_dir = tmp_path / "backups"
    data_dir = tmp_path / "data"
    env = {**os.environ, "MNEMLET_DATA_DIR": str(data_dir)}

    result = subprocess.run(
        [".venv/bin/mnemlet", "backup", "--output", str(output_dir)],
        check=True,
        cwd=Path(__file__).parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    backup_path = Path(result.stdout.strip().removeprefix("Backup created: "))
    with tarfile.open(backup_path, "r:gz") as tar:
        assert "mnemlet.db" in tar.getnames()
    assert not (data_dir / "mnemlet.db").exists()

    restore_config = _config(tmp_path / "restore-target")
    restore_backup(restore_config, backup_path, confirm=True)
    restored_db = MnemletDB(restore_config.sqlite_path)
    try:
        assert "memories" in restored_db._list_tables()
    finally:
        restored_db.close()


def test_restore_rolls_back_directory_when_install_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_config = _config(tmp_path / "source")
    target_config = _config(tmp_path / "target")
    source_db = MnemletDB(source_config.sqlite_path)
    source_db.insert_memory(namespace="preferences", content_preview="source")
    source_db.close()
    (source_config.vault_path / "preferences").mkdir(parents=True)
    (source_config.vault_path / "preferences" / "new.md").write_text("new")
    backup_path = create_backup(source_config, output_dir=tmp_path / "backups")
    target_db = MnemletDB(target_config.sqlite_path)
    target_db.insert_memory(namespace="preferences", content_preview="target")
    target_db.close()
    target_config.vault_path.mkdir(parents=True)
    keep_file = target_config.vault_path / "keep.md"
    keep_file.write_text("keep")

    original_install = restore_module._install_staged_path

    def fail_install(staged: Path, destination: Path) -> None:
        if destination == target_config.vault_path:
            raise OSError("simulated install failure")
        original_install(staged, destination)

    monkeypatch.setattr(restore_module, "_install_staged_path", fail_install)

    with pytest.raises(OSError, match="simulated install failure"):
        restore_backup(target_config, backup_path, confirm=True)

    assert keep_file.read_text() == "keep"


def test_failed_restore_pre_backup_does_not_create_missing_target_db(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_config = _config(tmp_path / "source")
    target_config = _config(tmp_path / "target")
    source_db = MnemletDB(source_config.sqlite_path)
    source_db.insert_memory(namespace="preferences", content_preview="source")
    source_db.close()
    (source_config.vault_path / "preferences").mkdir(parents=True)
    (source_config.vault_path / "preferences" / "new.md").write_text("new")
    backup_path = create_backup(source_config, output_dir=tmp_path / "backups")
    target_config.vault_path.mkdir(parents=True)
    keep_file = target_config.vault_path / "keep.md"
    keep_file.write_text("keep")
    assert not target_config.sqlite_path.exists()

    original_install = restore_module._install_staged_path

    def fail_install(staged: Path, destination: Path) -> None:
        if destination == target_config.vault_path:
            raise OSError("simulated install failure")
        original_install(staged, destination)

    monkeypatch.setattr(restore_module, "_install_staged_path", fail_install)

    with pytest.raises(OSError, match="simulated install failure"):
        restore_backup(target_config, backup_path, confirm=True)

    assert keep_file.read_text() == "keep"
    assert not target_config.sqlite_path.exists()
