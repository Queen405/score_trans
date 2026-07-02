from __future__ import annotations

import html

from ....models.score import TextBlock


def _esc(value: str) -> str:
    return html.escape(value, quote=True)


def _extract_text_directives(text: str) -> tuple[str, list[TextBlock]]:
    lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "@text" or stripped.startswith("@text "):
            continue
        lines.append(line)
    return "\n".join(lines), []
