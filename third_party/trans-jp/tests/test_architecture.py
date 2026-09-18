from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

ROOT = Path(__file__).parents[1] / "trans_jp"
ALLOWED = {
    "models": set(),
    "raster": {"models"},
    "preprocess": {"models", "raster"},
    "structure": {"models", "raster"},
    "symbols": {"models", "raster"},
    "recognition": {"models"},
    "matching": {"models", "raster", "symbols"},
    "validation": {"models", "symbols"},
    "rendering": {"models"},
    "provenance": {"models"},
    "io": {"models"},
    "pipeline": {
        "models",
        "io",
        "preprocess",
        "structure",
        "recognition",
        "matching",
        "validation",
        "provenance",
        "rendering",
    },
}


def test_dependency_direction_and_no_backend_imports():
    violations = []
    for layer, allowed in ALLOWED.items():
        for path in (ROOT / layer).glob("*.py"):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                modules = []
                if isinstance(node, ast.ImportFrom):
                    name = node.module or ""
                    if node.level:
                        name = importlib.util.resolve_name(
                            "." * node.level + name, f"trans_jp.{layer}"
                        )
                    modules = [name]
                elif isinstance(node, ast.Import):
                    modules = [alias.name for alias in node.names]
                for name in modules:
                    assert not name.startswith("score_trans"), (path, name)
                    if name.startswith("trans_jp."):
                        dependency = name.split(".")[1]
                        if dependency != layer and dependency not in allowed:
                            violations.append((path.name, layer, dependency))
                    elif layer == "models":
                        import sys

                        assert name.split(".")[0] in sys.stdlib_module_names, (
                            path,
                            name,
                        )
    assert not violations


def test_pure_layers_do_not_open_files_or_exit_process():
    for layer in [
        "raster",
        "structure",
        "symbols",
        "matching",
        "validation",
        "rendering",
        "provenance",
        "models",
    ]:
        for path in (ROOT / layer).glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        assert node.func.id not in {"open", "exit", "quit"}, path
                    if isinstance(node.func, ast.Attribute):
                        assert node.func.attr not in {
                            "write_text",
                            "write_bytes",
                            "read_text",
                            "read_bytes",
                            "mkdir",
                            "unlink",
                        }, path
                if (
                    isinstance(node, ast.Raise)
                    and isinstance(node.exc, ast.Call)
                    and isinstance(node.exc.func, ast.Name)
                ):
                    assert node.exc.func.id != "SystemExit", path


def test_cli_does_not_contain_pipeline_logic():
    tree = ast.parse((ROOT / "cli.py").read_text(encoding="utf-8"))
    definitions = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
    assert definitions == {"parse_args", "setup_logging", "main", "run"}
