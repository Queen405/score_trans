from __future__ import annotations


def parse_optional_int(value: str, field_name: str) -> int | None:
    text = value.strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError as exc:
        raise ValueError(f"{field_name}必须是整数。") from exc
