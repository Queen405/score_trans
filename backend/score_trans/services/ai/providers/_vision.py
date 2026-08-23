from __future__ import annotations

from pathlib import Path
from typing import Any

from ....models.common.errors import AITranscriptionError
from ....utils.media import image_to_data_url
from ..core.config import AI_MAX_TOKENS, AI_SYSTEM_MSG, AI_TEMPERATURE
from ..core.parsing import parse_vision_page_result
from ..core.prompts import _load_prompt_config, build_jianpu_prompt
from ..core.schemas import VisionPageResult
from ._http import CompletionResult, chat_completions


class OpenAICompatibleVisionTranscriber:
    base_url: str
    model: str
    api_key: str
    timeout: float
    dry_run: bool
    # 0 表示未配置：回退到 AI_MAX_TOKENS（环境变量，再回退 4096）。
    max_tokens: int = 0
    extra_body: dict[str, Any] | None = None

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
                warnings=["dry_run: request was not sent"],
                confidence=1.0,
            )

        system_message = (
            _load_prompt_config().get("system_message")
            or AI_SYSTEM_MSG
            or "You are a careful sheet-music to numbered-notation transcription agent."
        )
        image_url = image_to_data_url(path)
        try:
            result = self._request_page(
                system_message=system_message,
                user_text=prompt,
                image_url=image_url,
            )
        except Exception as exc:
            raise AITranscriptionError(
                f"AI transcription request failed: {exc}"
            ) from exc

        content = result.content
        truncation_warnings: list[str] = []
        if result.finish_reason == "length":
            # 截断的 JSON 无法安全拼接续写：改用更紧凑的提示完整重试一次。
            compact_prompt = build_jianpu_prompt(
                target_key=target_key,
                title=title,
                page_index=page_index,
                extra_prompt=extra_prompt,
                compact=True,
            )
            try:
                retry_result = self._request_page(
                    system_message=system_message,
                    user_text=compact_prompt,
                    image_url=image_url,
                )
            except Exception as exc:
                raise AITranscriptionError(
                    f"AI transcription retry failed: {exc}"
                ) from exc
            if retry_result.finish_reason == "length":
                raise AITranscriptionError(
                    f"AI 转写输出达到 max_tokens 上限（{self.max_tokens or AI_MAX_TOKENS}）被截断，"
                    "紧凑提示重试仍未完成。请调大该 provider 的 max_tokens 或拆分乐谱页面。"
                )
            content = retry_result.content
            truncation_warnings.append(
                "初次响应因 token 上限截断，已使用紧凑提示重试。"
            )

        parsed = parse_vision_page_result(content)
        if truncation_warnings:
            parsed.warnings = [*truncation_warnings, *parsed.warnings]
        return parsed

    def _request_page(
        self,
        *,
        system_message: str,
        user_text: str,
        image_url: str,
    ) -> CompletionResult:
        messages = [
            {"role": "system", "content": system_message},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_text},
                    {
                        "type": "image_url",
                        "image_url": {"url": image_url},
                    },
                ],
            },
        ]
        return chat_completions(
            base_url=self.base_url,
            api_key=self.api_key,
            model=self.model,
            messages=messages,
            temperature=AI_TEMPERATURE,
            timeout=self.timeout,
            max_tokens=self.max_tokens or AI_MAX_TOKENS,
            response_format={"type": "json_object"},
            extra_body=self.extra_body,
        )
