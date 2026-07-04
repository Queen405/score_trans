from __future__ import annotations

import html


def _esc(value: str) -> str:
    return html.escape(value, quote=True)


def _strip_legacy_text_directives(text: str) -> str:
    """Remove deprecated inline text directives from Jianpu source.

    OCR and editor text placement is represented by structured ``TextBlock``
    values.  Legacy ``@text`` lines are deliberately ignored so stale source
    text cannot override those authoritative attachments.
    """
    lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "@text" or stripped.startswith("@text "):
            continue
        lines.append(line)
    return "\n".join(lines)
