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
    text = re.sub(r"^```(?:json)?\s*\n?", "", text).strip()
    text = re.sub(r"\n?```\s*$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        return _repair_truncated_json(text)


def _repair_truncated_json(text: str) -> Any:
    """Attempt to extract a valid object from a truncated JSON string.

    When the LLM output exceeds max_tokens, the JSON is cut off mid-value.
    This function tries to close any open string and object, then parse.
    """
    match = re.search(r"\{.*", text, flags=re.DOTALL)
    if not match:
        raise json.JSONDecodeError("No JSON object found", text, 0)
    partial = match.group(0)
    in_string = False
    escape = False
    for char in partial:
        if escape:
            escape = False
        elif char == "\\":
            escape = True
        elif char == '"':
            in_string = not in_string
    if in_string:
        partial += '"'
    partial += "}"
    try:
        return json.loads(partial)
    except json.JSONDecodeError:
        raise
