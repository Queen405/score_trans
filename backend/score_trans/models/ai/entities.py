from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class AiChatSession:
    id: str
    title: str
    created_at: str
    updated_at: str


@dataclass(slots=True)
class AiChatMessage:
    id: int
    session_id: str
    role: str
    content: str
    created_at: str
