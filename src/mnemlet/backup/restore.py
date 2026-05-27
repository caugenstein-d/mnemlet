"""Restore Mnémlet data from portable backup archives."""

from __future__ import annotations

import shutil
import tarfile
import tempfile
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
        staged_vault = _stage_directory(temp_dir / "vault", temp_dir / "staged-vault")
        staged_chroma = _stage_directory(temp_dir / "chroma", temp_dir / "staged-chroma")
        pre_restore_backup = create_backup(config, output_dir=config.data_dir.parent / "pre-restore-backups")

        _replace_file(temp_dir / "mnemlet.db", config.sqlite_path)
        for suffix in ("-wal", "-shm"):
            source = temp_dir / f"mnemlet.db{suffix}"
            target = Path(f"{config.sqlite_path}{suffix}")
            if source.exists():
                _replace_file(source, target)
            elif target.exists():
                target.unlink()
        _replace_with_staged_directory(staged_vault, config.vault_path)
        _replace_with_staged_directory(staged_chroma, config.chroma_path)

    return {
        "restored_from": str(backup_path),
        "pre_restore_backup": str(pre_restore_backup),
        "data_dir": str(config.data_dir),
    }


def _validate_extracted_backup(temp_dir: Path) -> None:
    """Validate restored archive contents before modifying target data."""
    db_path = temp_dir / "mnemlet.db"
    if not db_path.is_file():
        raise ValueError("Backup archive must contain mnemlet.db as a regular file")
    for name in ("mnemlet.db-wal", "mnemlet.db-shm"):
        sidecar = temp_dir / name
        if sidecar.exists() and not sidecar.is_file():
            raise ValueError(f"Backup archive entry {name} must be a regular file")
    for name in ("vault", "chroma"):
        directory = temp_dir / name
        if directory.exists() and not directory.is_dir():
            raise ValueError(f"Backup archive entry {name} must be a directory")


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


def _replace_file(source: Path, target: Path) -> None:
    """Replace a target file with a restored source file if present."""
    if not source.exists():
        if target.exists():
            target.unlink()
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def _stage_directory(source: Path, staging_path: Path) -> Path | None:
    """Copy a restored directory into staging before target replacement."""
    if not source.exists():
        return None
    shutil.copytree(source, staging_path)
    return staging_path


def _replace_with_staged_directory(staged: Path | None, target: Path) -> None:
    """Replace a target directory with a validated staged directory."""
    if target.exists():
        shutil.rmtree(target)
    if staged is not None:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(staged), target)
