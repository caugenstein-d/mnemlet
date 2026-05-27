"""Restore Mnémlet data from portable backup archives."""

from __future__ import annotations

import os
import shutil
import sqlite3
import tarfile
import tempfile
import uuid
from pathlib import Path
from typing import Any

from mnemlet.backup.backup import create_backup
from mnemlet.config import MnemletConfig


def restore_backup(config: MnemletConfig, backup_path: Path, confirm: bool = False) -> dict[str, Any]:
    """Restore a backup archive into the configured data paths."""
    if not backup_path.exists():
        raise FileNotFoundError(f"Backup not found: {backup_path}")
    if not confirm and _target_has_data(config):
        raise RuntimeError("Refusing to restore into a non-empty target without confirm=True")

    config.data_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="mnemlet-restore-", dir=config.data_dir.parent) as temp_name:
        temp_dir = Path(temp_name)
        with tarfile.open(backup_path, "r:gz") as tar:
            tar.extractall(temp_dir, filter="data")

        _validate_extracted_backup(temp_dir)
        replacements = _stage_replacements(config, temp_dir)
        pre_restore_backup = create_backup(config, output_dir=config.data_dir.parent / "pre-restore-backups")
        _apply_replacements(replacements)

    return {
        "restored_from": str(backup_path),
        "pre_restore_backup": str(pre_restore_backup),
        "data_dir": str(config.data_dir),
    }


def _stage_replacements(config: MnemletConfig, temp_dir: Path) -> list[tuple[Path, Path | None]]:
    """Stage all restore targets on their target filesystems before mutation."""
    replacements: list[tuple[Path, Path | None]] = [
        (config.sqlite_path, _stage_file(temp_dir / "mnemlet.db", config.sqlite_path)),
    ]
    for suffix in ("-wal", "-shm"):
        source = temp_dir / f"mnemlet.db{suffix}"
        target = Path(f"{config.sqlite_path}{suffix}")
        replacements.append((target, _stage_file(source, target) if source.exists() else None))
    replacements.append((config.vault_path, _stage_directory(temp_dir / "vault", config.vault_path)))
    replacements.append((config.chroma_path, _stage_directory(temp_dir / "chroma", config.chroma_path)))
    return replacements


def _validate_extracted_backup(temp_dir: Path) -> None:
    """Validate restored archive contents before modifying target data."""
    db_path = temp_dir / "mnemlet.db"
    if not db_path.is_file():
        raise ValueError("Backup archive must contain mnemlet.db as a regular file")
    _validate_sqlite_database(db_path)
    for name in ("mnemlet.db-wal", "mnemlet.db-shm"):
        sidecar = temp_dir / name
        if sidecar.exists() and not sidecar.is_file():
            raise ValueError(f"Backup archive entry {name} must be a regular file")
    for name in ("vault", "chroma"):
        directory = temp_dir / name
        if directory.exists() and not directory.is_dir():
            raise ValueError(f"Backup archive entry {name} must be a directory")


def _validate_sqlite_database(db_path: Path) -> None:
    """Validate that an extracted backup DB is a readable Mnémlet SQLite database."""
    with tempfile.TemporaryDirectory(prefix="mnemlet-validate-") as temp_name:
        validation_db_path = Path(temp_name) / "mnemlet.db"
        shutil.copy2(db_path, validation_db_path)
        for suffix in ("-wal", "-shm"):
            sidecar = Path(f"{db_path}{suffix}")
            if sidecar.exists():
                shutil.copy2(sidecar, Path(f"{validation_db_path}{suffix}"))
        _validate_sqlite_database_copy(validation_db_path)


def _validate_sqlite_database_copy(db_path: Path) -> None:
    """Validate a temporary SQLite DB copy where WAL/SHM may be updated."""
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            conn.execute("PRAGMA query_only=ON")
            integrity = conn.execute("PRAGMA integrity_check").fetchone()
            if integrity is None or integrity[0] != "ok":
                raise ValueError("Backup mnemlet.db failed SQLite integrity_check")
            row = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'memories'"
            ).fetchone()
            if row is None:
                raise ValueError("Backup mnemlet.db is missing required memories table")
        finally:
            conn.close()
    except sqlite3.DatabaseError as exc:
        raise ValueError("Backup mnemlet.db is not a valid SQLite database") from exc


def _target_has_data(config: MnemletConfig) -> bool:
    """Return whether any configured restore target currently has data."""
    paths = [
        config.sqlite_path,
        Path(f"{config.sqlite_path}-wal"),
        Path(f"{config.sqlite_path}-shm"),
        config.vault_path,
        config.chroma_path,
    ]
    for path in paths:
        if path.is_file():
            return True
        if path.is_dir() and any(path.iterdir()):
            return True
    return False


def _stage_file(source: Path, target: Path) -> Path:
    """Copy a restored file into a target-local staging file."""
    target.parent.mkdir(parents=True, exist_ok=True)
    handle, staging_name = tempfile.mkstemp(prefix=f".{target.name}.restore-", dir=target.parent)
    os.close(handle)
    staging_path = Path(staging_name)
    shutil.copy2(source, staging_path)
    return staging_path


def _stage_directory(source: Path, target: Path) -> Path | None:
    """Copy a restored directory into a target-local staging directory."""
    if not source.exists():
        return None
    target.parent.mkdir(parents=True, exist_ok=True)
    staging_path = Path(tempfile.mkdtemp(prefix=f".{target.name}.restore-", dir=target.parent))
    staging_path.rmdir()
    shutil.copytree(source, staging_path)
    return staging_path


def _apply_replacements(replacements: list[tuple[Path, Path | None]]) -> None:
    """Install staged restore targets and roll back moved-aside originals on failure."""
    moved: list[tuple[Path, Path]] = []
    installed: list[Path] = []
    try:
        for target, staged in replacements:
            moved_aside = _move_existing_aside(target)
            if moved_aside is not None:
                moved.append((target, moved_aside))
            if staged is not None:
                _install_staged_path(staged, target)
                installed.append(target)
    except Exception:
        _rollback_replacements(moved, installed)
        raise
    for _target, moved_aside in moved:
        _remove_path(moved_aside)


def _move_existing_aside(target: Path) -> Path | None:
    """Move an existing restore target to a unique sibling path."""
    if not target.exists():
        return None
    moved_aside = target.parent / f".{target.name}.restore-old-{uuid.uuid4().hex}"
    target.rename(moved_aside)
    return moved_aside


def _install_staged_path(staged: Path, target: Path) -> None:
    """Install a staged file or directory at its live target path."""
    target.parent.mkdir(parents=True, exist_ok=True)
    os.replace(staged, target)


def _rollback_replacements(moved: list[tuple[Path, Path]], installed: list[Path]) -> None:
    """Restore moved-aside targets after a failed restore installation."""
    for target in reversed(installed):
        _remove_path(target)
    for target, moved_aside in reversed(moved):
        if target.exists():
            _remove_path(target)
        moved_aside.rename(target)


def _remove_path(path: Path) -> None:
    """Remove a file or directory restore artifact."""
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()
