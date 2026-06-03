from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, Field

from ...models.common.errors import AITranscriptionError


DEFAULT_AI_BASE_URL = "https://api.siliconflow.cn/v1"
DEFAULT_AI_MODEL = "Qwen/Qwen3-VL-8B-Instruct"


class VisionPageResult(BaseModel):
    title: str | None = None
    key: str | None = None
    meter: str | None = None
    tempo: str | None = None
    jianpu_text: str
    warnings: list[str] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0, le=1)


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


class MockVisionJianpuProvider:
    def __init__(self, results: list[VisionPageResult] | None = None) -> None:
        self.results = list(results or [])
        self.calls: list[Path] = []

    def transcribe_page(
        self,
        image_path: str | Path,
        *,
        target_key: str = "C",
        title: str | None = None,
        page_index: int = 0,
        extra_prompt: str | None = None,
    ) -> VisionPageResult:
        self.calls.append(Path(image_path))
        if self.results:
            return self.results[min(page_index, len(self.results) - 1)]
        return VisionPageResult(
            title=title,
            key=target_key,
            meter="4/4",
            jianpu_text=f"title={title or 'AI 简谱'}\n1={target_key}\n4/4\n1 2 3 4 |",
            warnings=[],
            confidence=1.0,
        )


class LangChainVisionJianpuProvider:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        timeout: float = 120.0,
        dry_run: bool = False,
    ) -> None:
        persisted = persisted_ai_settings()
        self.base_url = (
            base_url
            or os.getenv("SCORE_TRANS_AI_BASE_URL")
            or persisted.get("ai_base_url")
            or DEFAULT_AI_BASE_URL
        ).rstrip("/")
        self.model = (
            model
            or os.getenv("SCORE_TRANS_AI_MODEL")
            or persisted.get("ai_model")
            or DEFAULT_AI_MODEL
        )
        self.api_key = (
            api_key
            or os.getenv("SCORE_TRANS_AI_API_KEY")
            or persisted.get("ai_api_key")
            or ""
        )
        self.timeout = timeout
        self.dry_run = dry_run

    def transcribe_page(
        self,
        image_path: str | Path,
        *,
        target_key: str = "C",
        title: str | None = None,
        page_index: int = 0,
        extra_prompt: str | None = None,
    ) -> VisionPageResult:
        path = Path(image_path)
        if not path.is_file():
            raise FileNotFoundError(path)
        if not self.api_key and not self.dry_run:
            raise AITranscriptionError("AI API key not configured. Set it in Settings.")

        prompt = build_jianpu_prompt(
            target_key=target_key,
            title=title,
            page_index=page_index,
            extra_prompt=extra_prompt,
        )
        if self.dry_run:
            return VisionPageResult(
                title=title,
                key=target_key,
                meter="4/4",
                jianpu_text=f"title={title or 'AI 简谱'}\n1={target_key}\n4/4\n1 2 3 4 |",
                warnings=["dry_run: LangChain request was not sent"],
                confidence=1.0,
            )

        try:
            from langchain_core.messages import HumanMessage, SystemMessage
            from langchain_openai import ChatOpenAI
        except ImportError as exc:
            raise AITranscriptionError(
                "LangChain vision dependencies are not installed. "
                "Install langchain and langchain-openai."
            ) from exc

        llm = ChatOpenAI(
            model=self.model,
            base_url=self.base_url,
            api_key=self.api_key,
            temperature=0,
            timeout=self.timeout,
            model_kwargs={"response_format": {"type": "json_object"}},
        )
        messages = [
            SystemMessage(content="You are a careful sheet-music to numbered-notation transcription agent."),
            HumanMessage(
                content=[
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_to_data_url(path)}},
                ]
            ),
        ]
        try:
            response = llm.invoke(messages)
        except Exception as exc:
            raise AITranscriptionError(f"AI transcription request failed: {exc}") from exc

        return parse_vision_page_result(getattr(response, "content", response))


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
    title_hint = f"用户给定标题：{title}\n" if title else ""
    extra = f"\n额外要求：\n{extra_prompt.strip()}\n" if extra_prompt and extra_prompt.strip() else ""
    return (
        "请把这张乐谱图片转写成本项目的简谱文本语法，并只返回 JSON。\n"
        f"页码索引：{page_index + 1}\n"
        f"{title_hint}"
        f"目标简谱调：1={target_key}\n\n"
        "项目简谱语法：\n"
        "- title=曲名 可选；1=C 表示调号；4/4 表示拍号；tempo=85 可选。\n"
        "- 1 到 7 表示音级，0 表示休止符；#1、b7、n4 表示临时升降/还原。\n"
        "- 1' 表示高八度，1, 表示低八度。\n"
        "- 默认音符是四分音符；w/h/q/s/d 前缀分别表示全音符、二分、八分、十六分、三十二分。\n"
        "- 附点写作 1. 或 q2.；延长写作 1-、1---；和弦写作 [1+3+5] 或 q[#2+4'+6]。\n"
        "- 小节线写作 |，反复可写 |: :|；圆滑线写作 (1 2 3)；延音线写作 1~ ~1。\n"
        "- 歌词用 L: 开头，按音符顺序排列，例如 L: 春 风 又 绿。\n\n"
        "转写要求：\n"
        "1. 如果源谱是五线谱，请根据调号和目标调把音高转换为 1-7。\n"
        "2. 尽量保留拍号、调号、标题、速度、歌词、小节线、休止符、附点、连线、反复记号。\n"
        "3. 每个小节的时值尽量与拍号一致；不确定的地方先选最可能的写法，并写入 warnings。\n"
        "4. 看不清的音不要编造复杂解释，可用 0 或相邻时值兜底，并在 warnings 说明页内位置。\n"
        "5. jianpu_text 字段必须是可直接放入编辑器的完整文本，至少包含 1=调号 和 拍号。\n\n"
        "JSON 格式：\n"
        '{"title":null,"key":"C","meter":"4/4","tempo":null,'
        '"jianpu_text":"1=C\\n4/4\\n1 2 3 4 |",'
        '"warnings":[],"confidence":0.0}'
        f"{extra}"
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
