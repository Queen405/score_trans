from __future__ import annotations

import re
from typing import Any

from ...models.score import TextRole


def cleaned_plain_text_lines(text: str) -> list[str]:
    stripped = text.strip()
    if stripped.startswith('"""') and stripped.endswith('"""'):
        stripped = stripped[3:-3].strip()
    lines = []
    seen = set()
    for line in stripped.splitlines():
        line = clean_plain_text_line(line)
        key = line.casefold()
        if line and key not in seen:
            lines.append(line)
            seen.add(key)
    return lines


def clean_plain_text_line(line: str) -> str:
    line = line.strip().strip("`")
    for marker in (
        "The text in the image",
        "The image contains",
        "The text reads",
        "Text in the image",
        "Visible text",
    ):
        if marker in line:
            line = line.split(marker, 1)[0].strip()
    line = re.sub(r"^\d+\.\s+(?=[A-Za-z\u4e00-\u9fff])", "", line)
    line = line.strip(":： \t")
    line = collapse_exact_repetition(line)
    if not line:
        return ""
    lowered = line.lower()
    if lowered in {
        "the text reads",
        "the text in the image is",
        "the image contains the following text",
    }:
        return ""
    return line


def collapse_exact_repetition(text: str) -> str:
    value = text.strip()
    while value and len(value) % 2 == 0 and value[: len(value) // 2] == value[len(value) // 2 :]:
        value = value[: len(value) // 2].strip()
    return value


def infer_text_role(text: str) -> TextRole:
    lowered = text.lower()
    if re.search(r"\b(allegro|andante|moderato|largo|adagio|presto|rit\.?|accel\.?)\b", lowered):
        return "expression"
    if re.search(r"\b\d+\s*=\s*[A-Ga-g]", text):
        return "expression"
    if re.fullmatch(r"\d+", text.strip()):
        return "measure_number"
    return "other"


def normalize_text_role(value: Any, text: str) -> TextRole:
    role = str(value or "").strip().lower().replace("-", "_")
    aliases = {
        "tempo": "expression",
        "dynamic": "expression",
        "dynamics": "expression",
        "expression_text": "expression",
        "bar_number": "measure_number",
        "measure": "measure_number",
        "measure_no": "measure_number",
        "measure_num": "measure_number",
        "lyrics": "lyric",
        "annotation": "other",
        "unknown": "other",
    }
    normalized = aliases.get(role, role)
    if normalized in TextRole.__args__:
        return normalized  # type: ignore[return-value]
    return infer_text_role(text)
