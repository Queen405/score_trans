from __future__ import annotations

import shutil
from pathlib import Path


def migrate_legacy_sqlite(target: Path, legacy: Path) -> None:
    """Best-effort copy of an old SQLite database into the user data directory."""
    if target.exists() or not legacy.exists() or _same_path(target, legacy):
        return

    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copy2(legacy, target)
        for suffix in ("-wal", "-shm"):
            legacy_sidecar = Path(f"{legacy}{suffix}")
            if legacy_sidecar.exists():
                shutil.copy2(legacy_sidecar, Path(f"{target}{suffix}"))
    except OSError:
        return


def _same_path(left: Path, right: Path) -> bool:
    try:
        return left.resolve() == right.resolve()
    except OSError:
        return False
