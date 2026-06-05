from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ...base import (
    DEFAULT_AI_BASE_URL,
    DEFAULT_AI_MODEL,
    VisionPageResult,
    VisionJianpuProvider,
    build_jianpu_prompt,
    image_to_data_url,
    parse_vision_page_result,
    persisted_ai_settings,
    _load_prompt_config,
)
from ...registry import register_provider
from .....models.common.errors import AITranscriptionError


class LangChainVisionJianpuProvider:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        timeout: float = float(os.getenv("SCORE_TRANS_AI_TIMEOUT", "120.0")),
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
            temperature=float(os.getenv("SCORE_TRANS_AI_TEMPERATURE", "0")),
            timeout=self.timeout,
            model_kwargs={"response_format": {"type": "json_object"}},
        )
        messages = [
            SystemMessage(content=_load_prompt_config().get("system_message", os.getenv("SCORE_TRANS_AI_SYSTEM_MSG", "You are a careful sheet-music to numbered-notation transcription agent."))),
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


register_provider("openai_compatible", LangChainVisionJianpuProvider)
register_provider("siliconflow", LangChainVisionJianpuProvider)
