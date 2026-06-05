"""Dictionary utility helpers."""

from __future__ import annotations

from typing import Any


def first_present(raw: dict[str, Any], keys: tuple[str, ...]) -> Any:
    """Return the value for the first key that exists and is not None."""
    for key in keys:
        if key in raw and raw[key] is not None:
            return raw[key]
    return None
