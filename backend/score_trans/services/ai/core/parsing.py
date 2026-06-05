from __future__ import annotations

import json
import re
from typing import Any

from ....models.common.errors import AITranscriptionError
from ....utils.json_parsing import content_to_text, parse_json_content
from .schemas import VisionPageResult


def parse_vision_page_result(content: Any) -> VisionPageResult:
    text = content_to_text(content)
    try:
        payload = parse_json_content(content)
    except (json.JSONDecodeError, AITranscriptionError) as exc:
        if looks_like_jianpu_text(text):
            return VisionPageResult(
                jianpu_text=text,
                warnings=["AI response was not JSON; used plain text transcription fallback."],
                confidence=None,
            )
        raise AITranscriptionError("AI transcription response was not valid JSON.") from exc

    if not isinstance(payload, dict):
        raise AITranscriptionError("AI transcription JSON must be an object.")
    if isinstance(payload.get("jianpu_text"), dict):
        payload["jianpu_text"] = json.dumps(payload["jianpu_text"], ensure_ascii=False)
    if not str(payload.get("jianpu_text") or "").strip():
        raise AITranscriptionError("AI transcription JSON must contain jianpu_text.")

    try:
        return VisionPageResult.model_validate(payload)
    except Exception as exc:
        raise AITranscriptionError(f"AI transcription JSON does not match schema: {exc}") from exc


def looks_like_jianpu_text(text: str) -> bool:
    if not text.strip():
        return False
    if re.search(r"(?m)^\s*(title=|1\s*=|\d+\s*/\s*\d+)", text):
        return True
    return bool(re.search(r"(^|\s)(?:[whqsd]?[#bnx]?[1-7][',]*|[whqsd]?0|\[[^\]]+\])(\s|\||$)", text))
