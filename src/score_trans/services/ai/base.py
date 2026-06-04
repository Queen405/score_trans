from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from ...config import CONFIG_DIR
from ...models.common.errors import AITranscriptionError


DEFAULT_AI_BASE_URL = "https://api.siliconflow.cn/v1"
DEFAULT_AI_MODEL = "Qwen/Qwen3-VL-8B-Instruct"

_PROMPT_CONFIG: dict[str, str] | None = None


def _load_prompt_config() -> dict[str, str]:
    global _PROMPT_CONFIG
    if _PROMPT_CONFIG is not None:
        return _PROMPT_CONFIG
    config_path = CONFIG_DIR / "ai_prompt.json"
    if config_path.is_file():
        with open(config_path, encoding="utf-8") as f:
            _PROMPT_CONFIG = json.load(f)
    else:
        _PROMPT_CONFIG = {}
    return _PROMPT_CONFIG


def _cfg_value(cfg: dict[str, str], key: str) -> str:
    if key in cfg:
        return cfg[key]
    raise AITranscriptionError(
        f"ai_prompt.json 缺少必填字段 '{key}'。"
        "请在 {CONFIG_DIR / 'ai_prompt.json'} 中配置。"
    )


class VisionPageResult(BaseModel):
    title: str | None = None
    key: str | None = None
    meter: str | None = None
    tempo: str | None = None
    jianpu_text: str
    warnings: list[str] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0, le=1)


@runtime_checkable
class VisionJianpuProvider(Protocol):
    def transcribe_page(
        self,
        image_path: str | Path,
        *,
        target_key: str = "C",
        title: str | None = None,
        page_index: int = 0,
        extra_prompt: str | None = None,
    ) -> VisionPageResult:
        """Return one page of score transcription as project Jianpu syntax."""


def persisted_ai_settings() -> dict[str, str]:
    try:
        from ..settings.settings_service import SettingsService

        return SettingsService().get_all()
    except Exception:
        return {}


def image_to_data_url(path: Path) -> str:
    mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def build_jianpu_prompt(
    *,
    target_key: str,
    title: str | None,
    page_index: int,
    extra_prompt: str | None,
) -> str:
    cfg = _load_prompt_config()
    template = _cfg_value(cfg, "prompt_template")
    title_hint = cfg.get("title_hint_template", "用户给定标题：{title}\n").format(title=title) if title else ""
    extra = ""
    if extra_prompt and extra_prompt.strip():
        extra = cfg.get("extra_prompt_template", "\n额外要求：\n{extra_prompt}\n").format(extra_prompt=extra_prompt.strip())
    syntax_rules = _cfg_value(cfg, "syntax_rules")
    transcription_rules = _cfg_value(cfg, "transcription_rules")
    hard_constraints = cfg.get("hard_constraints", "")
    json_schema = _cfg_value(cfg, "json_schema")
    return template.format(
        page_index=page_index + 1,
        title_hint=title_hint,
        target_key=target_key,
        syntax_rules=syntax_rules,
        transcription_rules=transcription_rules,
        hard_constraints=hard_constraints,
        json_schema=json_schema,
        extra=extra,
    )


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


def parse_json_content(content: Any) -> Any:
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


def content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "\n".join(parts).strip()
    if isinstance(content, BaseModel):
        return content.model_dump_json()
    if content is None:
        return ""
    return str(content).strip()
