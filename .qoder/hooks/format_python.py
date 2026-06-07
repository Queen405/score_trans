"""Post-edit hook: auto-format Python files with ruff. Skips non-.py files."""
from __future__ import annotations

import json
import subprocess
import sys


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        return

    file_path: str = data.get("file_path", "")
    if not file_path.endswith(".py"):
        return

    python = ".venv/Scripts/python.exe"
    for args in [["-m", "ruff", "format", file_path], ["-m", "ruff", "check", "--fix", file_path]]:
        subprocess.run([python, *args], check=False, capture_output=True)


if __name__ == "__main__":
    main()
