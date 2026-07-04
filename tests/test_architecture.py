from __future__ import annotations

import ast
from pathlib import Path
import re

from score_trans.api.request_limits import UPLOAD_PATHS


SRC_ROOT = Path(__file__).resolve().parents[1] / "backend" / "score_trans"
RENDERER_ROOT = (
    Path(__file__).resolve().parents[1] / "desktop" / "src" / "renderer" / "src"
)

LAYER_IMPORTS = {
    "api": {"config", "exec", "models"},
    "exec": {"config", "models", "services", "utils"},
    "services": {"config", "dao", "domain", "models", "utils"},
    "dao": {"models", "utils"},
    "domain": {"models", "utils"},
    "models": set(),
}

KNOWN_LAYER_VIOLATIONS = {
    ("exec/convert/actions.py", "domain"),
    ("exec/export/actions.py", "domain"),
    ("exec/notation/actions.py", "domain"),
    ("exec/pipeline/actions.py", "domain"),
    ("exec/render/actions.py", "domain"),
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


def test_models_and_dao_do_not_import_config() -> None:
    offenders: list[str] = []
    for layer in ("models", "dao"):
        for file in _python_files(SRC_ROOT / layer):
            if "config" in _project_import_layers(file):
                offenders.append(file.relative_to(SRC_ROOT).as_posix())

    assert offenders == []


def test_utils_do_not_import_config() -> None:
    offenders = [
        file.relative_to(SRC_ROOT).as_posix()
        for file in _python_files(SRC_ROOT / "utils")
        if "config" in _project_import_layers(file)
    ]

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


def test_no_fastapi_imports_outside_api() -> None:
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

    assert offenders == set()


def test_blocking_api_actions_are_offloaded() -> None:
    blocking_methods = {
        "clear_cache",
        "create_chat_session_response",
        "delete_chat_session",
        "delete_file",
        "download_file",
        "export_midi",
        "export_midi_text",
        "export_musicxml",
        "export_musicxml_text",
        "files_exist",
        "get_chat_message_responses",
        "get_settings",
        "list_chat_session_responses",
        "update_settings",
        "upload_file",
    }
    offenders: list[str] = []
    for file in _python_files(SRC_ROOT / "api"):
        tree = ast.parse(file.read_text(encoding="utf-8-sig"))
        for function in (
            node for node in ast.walk(tree) if isinstance(node, ast.AsyncFunctionDef)
        ):
            for call in (
                node for node in ast.walk(function) if isinstance(node, ast.Call)
            ):
                if (
                    isinstance(call.func, ast.Attribute)
                    and isinstance(call.func.value, ast.Name)
                    and call.func.value.id == "actions"
                    and call.func.attr in blocking_methods
                ):
                    offenders.append(
                        f"{file.relative_to(SRC_ROOT).as_posix()}:{function.name}"
                    )

    assert offenders == []


def test_runtime_validation_paths_do_not_use_assert_statements() -> None:
    runtime_validation_files = [
        SRC_ROOT / "exec" / "convert" / "actions.py",
        SRC_ROOT / "services" / "render" / "drawing" / "spanners.py",
    ]
    offenders = []
    for file in runtime_validation_files:
        tree = ast.parse(file.read_text(encoding="utf-8-sig"))
        if any(isinstance(node, ast.Assert) for node in ast.walk(tree)):
            offenders.append(file.relative_to(SRC_ROOT).as_posix())

    assert offenders == []


def test_renderer_network_requests_use_authenticated_client() -> None:
    raw_fetch = re.compile(r"\bfetch\s*\(")
    allowed_fetch_file = RENDERER_ROOT / "api" / "client.ts"
    offenders: list[str] = []

    for pattern in ("*.ts", "*.vue"):
        for file in RENDERER_ROOT.rglob(pattern):
            text = file.read_text(encoding="utf-8")
            relative = file.relative_to(RENDERER_ROOT).as_posix()
            if file != allowed_fetch_file and raw_fetch.search(text):
                offenders.append(f"{relative}: raw fetch")
            if "new EventSource(" in text:
                offenders.append(f"{relative}: unauthenticated EventSource")

    assert offenders == []


def test_xml_parsing_uses_the_bounded_safe_parser() -> None:
    safe_parser = SRC_ROOT / "utils" / "safe_xml.py"
    offenders = [
        file.relative_to(SRC_ROOT).as_posix()
        for file in _python_files(SRC_ROOT)
        if file != safe_parser
        and re.search(
            r"\b(?:ET|ElementTree)\.(?:fromstring|parse)\s*\(",
            file.read_text(encoding="utf-8-sig"),
        )
    ]

    assert offenders == []


def test_all_upload_routes_have_request_body_limits() -> None:
    discovered: set[str] = set()
    for file in _python_files(SRC_ROOT / "api"):
        tree = ast.parse(file.read_text(encoding="utf-8-sig"))
        prefix = ""
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            if not any(
                isinstance(target, ast.Name) and target.id == "router"
                for target in node.targets
            ):
                continue
            if not isinstance(node.value, ast.Call):
                continue
            for keyword in node.value.keywords:
                if (
                    keyword.arg == "prefix"
                    and isinstance(keyword.value, ast.Constant)
                    and isinstance(keyword.value.value, str)
                ):
                    prefix = keyword.value.value

        for function in (
            node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ):
            annotations = [
                ast.unparse(argument.annotation)
                for argument in function.args.args
                if argument.annotation is not None
            ]
            if not any("UploadFile" in annotation for annotation in annotations):
                continue
            for decorator in function.decorator_list:
                if not (
                    isinstance(decorator, ast.Call)
                    and isinstance(decorator.func, ast.Attribute)
                    and decorator.func.attr in {"post", "put", "patch"}
                    and decorator.args
                    and isinstance(decorator.args[0], ast.Constant)
                    and isinstance(decorator.args[0].value, str)
                ):
                    continue
                discovered.add(f"{prefix}{decorator.args[0].value}" or "/")

    assert discovered == set(UPLOAD_PATHS)
