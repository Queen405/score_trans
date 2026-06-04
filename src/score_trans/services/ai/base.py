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
    template = cfg.get("prompt_template", _FALLBACK_PROMPT_TEMPLATE)
    title_hint = (cfg.get("title_hint_template", "用户给定标题：{title}\n")).format(title=title) if title else ""
    extra = ""
    if extra_prompt and extra_prompt.strip():
        extra = (cfg.get("extra_prompt_template", "\n额外要求：\n{extra_prompt}\n")).format(extra_prompt=extra_prompt.strip())
    syntax_rules = cfg.get("syntax_rules", _FALLBACK_SYNTAX_RULES)
    transcription_rules = cfg.get("transcription_rules", _FALLBACK_TRANSCRIPTION_RULES)
    hard_constraints = cfg.get("hard_constraints", "")
    json_schema = cfg.get("json_schema", _FALLBACK_JSON_SCHEMA)
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


_FALLBACK_PROMPT_TEMPLATE = (
    "请把这张乐谱图片转写成本项目的简谱文本语法，并只返回 JSON。\n"
    "页码索引：{page_index}\n"
    "{title_hint}"
    "目标简谱调：1={target_key}\n\n"
    "{syntax_rules}\n\n"
    "{transcription_rules}\n\n"
    "{hard_constraints}\n\n"
    "JSON 格式：\n{json_schema}"
    "{extra}"
)

_FALLBACK_SYNTAX_RULES = (
    "项目简谱语法：\n"
    "- title=曲名 可选；1=C 表示调号；4/4 表示拍号；tempo=85 可选。\n"
    "- 1 到 7 表示音级，0 表示休止符；#1、b7、n4 表示临时升降/还原。\n"
    "- 1' 表示高八度，1, 表示低八度。\n"
    "- 默认音符是四分音符；w/h/q/s/d 前缀分别表示全音符、二分、八分、十六分、三十二分。\n"
    "- 附点写作 1. 或 q2.；延长写作 1-、1---；和弦写作 [1+3+5] 或 q[#2+4'+6]。\n"
    "- 小节线写作 |，反复可写 |: :|；圆滑线写作 (1 2 3)；延音线写作 1~ ~1。"
)

_FALLBACK_TRANSCRIPTION_RULES = (
    "转写要求：\n"
    "1. 如果源谱是五线谱，请根据调号和目标调把音高转换为 1-7。\n"
    "2. 尽量保留拍号、调号、标题、速度、歌词、小节线、休止符、附点、连线、反复记号。\n"
    "3. 每个小节的时值尽量与拍号一致；不确定的地方先选最可能的写法，并写入 warnings。\n"
    "4. 看不清的音不要编造复杂解释，可用 0 或相邻时值兜底，并在 warnings 说明页内位置。\n"
    "5. jianpu_text 字段必须是可直接放入编辑器的完整文本，至少包含 1=调号 和 拍号。"
)

_FALLBACK_JSON_SCHEMA = (
    '{"title":null,"key":"C","meter":"4/4","tempo":null,'
    '"jianpu_text":"1=C\\n4/4\\n1 2 3 4 |",'
    '"warnings":[],"confidence":0.0}'
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
