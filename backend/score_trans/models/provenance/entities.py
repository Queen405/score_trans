from __future__ import annotations

from dataclasses import dataclass

from .schemas import TextAnchor


@dataclass(slots=True)
class JianpuDocument:
    text: str
    anchors: list[TextAnchor]
    text_hash: str
