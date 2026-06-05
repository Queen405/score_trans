"""JSON/content parsing helpers for LLM responses."""

from __future__ import annotations

import json
import re
from typing import Any


def content_to_text(content: Any) -> str:
    """Extract plain text from an LLM message content (str, list of dicts, dict, or None)."""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "\n".join(parts).strip()
    if isinstance(content, dict):
        return json.dumps(content, ensure_ascii=False)
    if content is None:
        return ""
    return str(content).strip()


def parse_json_content(content: Any) -> Any:
    """Parse JSON from an LLM message content, tolerating wrapper text."""
    if isinstance(content, dict):
        return content
    text = content_to_text(content)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))
