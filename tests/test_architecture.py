from __future__ import annotations

from pathlib import Path


SRC_ROOT = Path(__file__).resolve().parents[1] / "src" / "score_trans"


def _python_files(path: Path) -> list[Path]:
    return [
        file
        for file in path.rglob("*.py")
        if "__pycache__" not in file.parts
    ]


def test_api_layer_does_not_import_services_domain_or_dao() -> None:
    forbidden = (
        "score_trans.services",
        "score_trans.domain",
        "score_trans.dao",
        "from ..services",
        "from ...services",
        "from ..domain",
        "from ...domain",
        "from ..dao",
        "from ...dao",
    )

    offenders: list[str] = []
    for file in _python_files(SRC_ROOT / "api"):
        text = file.read_text(encoding="utf-8")
        if any(pattern in text for pattern in forbidden):
            offenders.append(str(file.relative_to(SRC_ROOT)))

    assert offenders == []


def test_dao_layer_does_not_import_api_exec_or_services() -> None:
    forbidden = (
        "score_trans.api",
        "score_trans.exec",
        "score_trans.services",
        "from ..api",
        "from ...api",
        "from ..exec",
        "from ...exec",
        "from ..services",
        "from ...services",
    )

    offenders: list[str] = []
    for file in _python_files(SRC_ROOT / "dao"):
        text = file.read_text(encoding="utf-8")
        if any(pattern in text for pattern in forbidden):
            offenders.append(str(file.relative_to(SRC_ROOT)))

    assert offenders == []

