from __future__ import annotations

import html
import re

from ....models.score import TextBlock


def _esc(value: str) -> str:
    return html.escape(value, quote=True)


def _split_measures(body: str) -> list[str]:
    measures = [measure.strip() for measure in re.split(r"\|", body) if measure.strip()]
    return measures or [body.strip()]


def _extract_text_directives(text: str) -> tuple[str, list[TextBlock]]:
    lines: list[str] = []
    blocks: list[TextBlock] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("@text "):
            block = _parse_text_directive(stripped)
            if block is not None:
                blocks.append(block)
            continue
        lines.append(line)
    return "\n".join(lines), blocks


def _parse_text_directive(line: str) -> TextBlock | None:
    parts = line.split(maxsplit=6)
    if len(parts) < 7:
        return None
    _mark, x1, y1, x2, y2, role, text = parts
    bbox = None
    if "-" not in {x1, y1, x2, y2}:
        try:
            bbox = (float(x1), float(y1), float(x2), float(y2))
        except ValueError:
            bbox = None
    if role not in {"title", "instrument", "lyric", "expression", "footer", "measure_number", "other"}:
        role = "other"
    return TextBlock(text=text.strip(), bbox=bbox, role=role)
