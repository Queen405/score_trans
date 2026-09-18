from __future__ import annotations


def utf16_length(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2
