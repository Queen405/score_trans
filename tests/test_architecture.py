from __future__ import annotations

import ast
from pathlib import Path


SRC_ROOT = Path(__file__).resolve().parents[1] / "backend" / "score_trans"

LAYER_IMPORTS = {
    "api": {"config", "exec", "models"},
    "exec": {"config", "models", "services", "utils"},
    "services": {"config", "dao", "domain", "models", "utils"},
    "dao": {"config", "models", "utils"},
    "domain": {"models", "utils"},
    "models": set(),
}

KNOWN_LAYER_VIOLATIONS = {
    ("exec/convert/actions.py", "domain"),
    ("exec/export/actions.py", "domain"),
    ("exec/notation/actions.py", "domain"),
    ("exec/pipeline/actions.py", "domain"),
    ("exec/render/actions.py", "domain"),
    ("models/ai/schemas.py", "config"),
    ("models/settings/schemas.py", "config"),
}

KNOWN_FASTAPI_IMPORTS_OUTSIDE_API = {
    "exec/export/actions.py",
    "exec/files/actions.py",
    "exec/history/actions.py",
    "exec/pipeline/actions.py",
    "exec/recognize/actions.py",
    "exec/render/actions.py",
    "services/files/upload_service.py",
}


def _python_files(path: Path) -> list[Path]:
    return [file for file in path.rglob("*.py") if "__pycache__" not in file.parts]


def _module_parts(file: Path) -> tuple[str, ...]:
    relative = file.relative_to(SRC_ROOT).with_suffix("")
    return ("score_trans", *relative.parts)


def _import_targets(
    source_module: tuple[str, ...],
    node: ast.Import | ast.ImportFrom,
) -> list[str]:
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    if node.level == 0:
        return [node.module] if node.module else []

    package = list(source_module[:-1])
    levels_up = node.level - 1
    if levels_up > len(package):
        return []
    if levels_up:
        package = package[:-levels_up]
    if node.module:
        package.extend(node.module.split("."))
    return [".".join(package)]


def _project_import_layers(file: Path) -> set[str]:
    source_module = _module_parts(file)
    layers: set[str] = set()
    tree = ast.parse(file.read_text(encoding="utf-8-sig"))
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        for target in _import_targets(source_module, node):
            parts = target.split(".")
            if len(parts) > 1 and parts[0] == "score_trans":
                layers.add(parts[1])
    return layers


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


def test_no_new_layer_import_violations() -> None:
    violations: set[tuple[str, str]] = set()
    for source_layer, allowed_layers in LAYER_IMPORTS.items():
        for file in _python_files(SRC_ROOT / source_layer):
            relative = file.relative_to(SRC_ROOT).as_posix()
            for imported_layer in _project_import_layers(file):
                if (
                    imported_layer in LAYER_IMPORTS
                    and imported_layer != source_layer
                    and imported_layer not in allowed_layers
                ):
                    violations.add((relative, imported_layer))

    unexpected = violations - KNOWN_LAYER_VIOLATIONS
    assert unexpected == set()


def test_no_new_fastapi_imports_outside_api() -> None:
    offenders: set[str] = set()
    for layer in ("exec", "services", "dao", "domain", "models"):
        for file in _python_files(SRC_ROOT / layer):
            tree = ast.parse(file.read_text(encoding="utf-8-sig"))
            if any(
                (
                    isinstance(node, ast.Import)
                    and any(alias.name == "fastapi" for alias in node.names)
                )
                or (isinstance(node, ast.ImportFrom) and node.module == "fastapi")
                for node in ast.walk(tree)
            ):
                offenders.add(file.relative_to(SRC_ROOT).as_posix())

    unexpected = offenders - KNOWN_FASTAPI_IMPORTS_OUTSIDE_API
    assert unexpected == set()
