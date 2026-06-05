"""Text cleaning and processing utilities."""

from __future__ import annotations

import re


def collapse_exact_repetition(text: str) -> str:
    """Collapse a string that is an exact concatenation of two identical halves."""
    value = text.strip()
    while value and len(value) % 2 == 0 and value[: len(value) // 2] == value[len(value) // 2 :]:
        value = value[: len(value) // 2].strip()
    return value


def clean_plain_text_line(line: str) -> str:
    """Clean a single line of OCR-extracted plain text."""
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


def cleaned_plain_text_lines(text: str) -> list[str]:
    """Split OCR text into cleaned, deduplicated lines."""
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
