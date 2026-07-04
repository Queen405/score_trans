from __future__ import annotations

from pathlib import Path

from score_trans.config import CONFIG_DIR as PUBLIC_CONFIG_DIR
from score_trans.models.common import paths
from score_trans.models.common.paths import (
    CONFIG_DIR,
    LEGACY_USER_DATA_DIR_NAME,
    USER_DATA_DIR_NAME,
    migrate_legacy_user_data_directory,
)


def test_config_directory_is_owned_by_the_path_model() -> None:
    assert PUBLIC_CONFIG_DIR == CONFIG_DIR
    assert CONFIG_DIR.name == "config"
    assert CONFIG_DIR.parent.name == "score_trans"


def test_user_data_directory_name_is_corrected() -> None:
    assert USER_DATA_DIR_NAME == ".score_trans"
    assert LEGACY_USER_DATA_DIR_NAME == ".sorce_trans"


def test_user_data_migration_copies_missing_files_without_overwriting(
    tmp_path: Path,
) -> None:
    legacy = tmp_path / LEGACY_USER_DATA_DIR_NAME
    target = tmp_path / USER_DATA_DIR_NAME
    (legacy / "work").mkdir(parents=True)
    (target / "work").mkdir(parents=True)
    (legacy / "work" / "history.db").write_bytes(b"legacy-history")
    (legacy / "work" / "settings.db").write_bytes(b"legacy-settings")
    (target / "work" / "settings.db").write_bytes(b"new-settings")

    assert migrate_legacy_user_data_directory(legacy, target) is True
    assert migrate_legacy_user_data_directory(legacy, target) is True

    assert (target / "work" / "history.db").read_bytes() == b"legacy-history"
    assert (target / "work" / "settings.db").read_bytes() == b"new-settings"
    assert (legacy / "work" / "settings.db").read_bytes() == b"legacy-settings"


def test_user_data_migration_fails_safe_for_symbolic_links(tmp_path: Path) -> None:
    legacy = tmp_path / LEGACY_USER_DATA_DIR_NAME
    target = tmp_path / USER_DATA_DIR_NAME
    external = tmp_path / "external.txt"
    legacy.mkdir()
    external.write_text("outside", encoding="utf-8")
    link = legacy / "linked.txt"
    try:
        link.symlink_to(external)
    except OSError:
        return

    assert migrate_legacy_user_data_directory(legacy, target) is False
    assert not (target / "linked.txt").exists()


def test_default_user_data_root_migrates_to_corrected_directory(
    tmp_path: Path, monkeypatch
) -> None:
    legacy = tmp_path / LEGACY_USER_DATA_DIR_NAME
    (legacy / "work").mkdir(parents=True)
    (legacy / "work" / "history.db").write_bytes(b"history")
    monkeypatch.delenv(paths.USER_DATA_DIR_ENV, raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    resolved = paths._resolve_user_data_root()

    assert resolved == (tmp_path / USER_DATA_DIR_NAME).resolve()
    assert (resolved / "work" / "history.db").read_bytes() == b"history"


def test_default_user_data_root_falls_back_when_initial_migration_fails(
    tmp_path: Path, monkeypatch
) -> None:
    legacy = tmp_path / LEGACY_USER_DATA_DIR_NAME
    legacy.mkdir()
    monkeypatch.delenv(paths.USER_DATA_DIR_ENV, raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(
        paths,
        "migrate_legacy_user_data_directory",
        lambda source, target: False,
    )

    assert paths._resolve_user_data_root() == legacy.resolve()
