from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

LlmProviderKind = Literal["ocr", "ai", "assistant"]


@dataclass(frozen=True, slots=True)
class LlmProviderProfile:
    id: str
    label: str
    provider: str
    base_url: str
    model: str
    description: str = ""
    fallback_model: str = ""


SILICONFLOW_BASE_URL = "https://api.siliconflow.cn/v1"
DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
XIAOMI_MIMO_BASE_URL = "https://api.xiaomimimo.com/v1"

DEFAULT_OCR_PROVIDER_ID = "siliconflow_deepseek_ocr"
DEFAULT_AI_PROVIDER_ID = "siliconflow_qwen3_vl_8b"
DEFAULT_ASSISTANT_PROVIDER_ID = "dashscope_deepseek_v4_flash"

OCR_PROVIDER_PROFILES: tuple[LlmProviderProfile, ...] = (
    LlmProviderProfile(
        id=DEFAULT_OCR_PROVIDER_ID,
        label="硅基流动 DeepSeek-OCR",
        provider="openai_compatible",
        base_url=SILICONFLOW_BASE_URL,
        model="deepseek-ai/DeepSeek-OCR",
        fallback_model="Qwen/Qwen3-VL-8B-Instruct",
        description="默认 OCR 识别；结果为空时回退到 Qwen3-VL-8B。",
    ),
    LlmProviderProfile(
        id="siliconflow_qwen3_vl_8b",
        label="硅基流动 Qwen3-VL-8B",
        provider="openai_compatible",
        base_url=SILICONFLOW_BASE_URL,
        model="Qwen/Qwen3-VL-8B-Instruct",
        description="OpenAI 兼容视觉模型，返回结构化 OCR 文本块。",
    ),
    LlmProviderProfile(
        id="dashscope_qwen_vl_ocr",
        label="百炼 qwen-vl-ocr",
        provider="dashscope",
        base_url=DASHSCOPE_BASE_URL,
        model="qwen-vl-ocr",
        description="阿里云百炼 OCR 模型。",
    ),
    LlmProviderProfile(
        id="dashscope_qwen_vl_max",
        label="百炼 qwen-vl-max",
        provider="dashscope",
        base_url=DASHSCOPE_BASE_URL,
        model="qwen-vl-max",
        description="阿里云百炼通用视觉模型。",
    ),
)

AI_PROVIDER_PROFILES: tuple[LlmProviderProfile, ...] = (
    LlmProviderProfile(
        id=DEFAULT_AI_PROVIDER_ID,
        label="硅基流动 Qwen3-VL-8B",
        provider="openai_compatible",
        base_url=SILICONFLOW_BASE_URL,
        model="Qwen/Qwen3-VL-8B-Instruct",
        description="默认 AI 视觉转写模型。",
    ),
    LlmProviderProfile(
        id="dashscope_qwen_vl_max",
        label="百炼 qwen-vl-max",
        provider="dashscope",
        base_url=DASHSCOPE_BASE_URL,
        model="qwen-vl-max",
        description="阿里云百炼视觉转写。",
    ),
    LlmProviderProfile(
        id="dashscope_qwen3_vl_plus",
        label="百炼 qwen3-vl-plus",
        provider="dashscope",
        base_url=DASHSCOPE_BASE_URL,
        model="qwen3-vl-plus",
        description="阿里云百炼 Qwen3-VL 视觉模型。",
    ),
    LlmProviderProfile(
        id="xiaomi_mimo_v25",
        label="小米 MiMo-V2.5",
        provider="xiaomi_mimo",
        base_url=XIAOMI_MIMO_BASE_URL,
        model="mimo-v2.5",
        description="MiMo 全模态视觉转写。",
    ),
)

ASSISTANT_PROVIDER_PROFILES: tuple[LlmProviderProfile, ...] = (
    LlmProviderProfile(
        id=DEFAULT_ASSISTANT_PROVIDER_ID,
        label="百炼 DeepSeek-V4-Flash",
        provider="dashscope",
        base_url=DASHSCOPE_BASE_URL,
        model="deepseek-v4-flash",
        description="默认工作台对话模型。",
    ),
    LlmProviderProfile(
        id="dashscope_qwen_plus",
        label="百炼 qwen-plus",
        provider="dashscope",
        base_url=DASHSCOPE_BASE_URL,
        model="qwen-plus",
        description="百炼通用对话模型。",
    ),
)

_PROFILES: dict[LlmProviderKind, tuple[LlmProviderProfile, ...]] = {
    "ocr": OCR_PROVIDER_PROFILES,
    "ai": AI_PROVIDER_PROFILES,
    "assistant": ASSISTANT_PROVIDER_PROFILES,
}
_DEFAULTS: dict[LlmProviderKind, str] = {
    "ocr": DEFAULT_OCR_PROVIDER_ID,
    "ai": DEFAULT_AI_PROVIDER_ID,
    "assistant": DEFAULT_ASSISTANT_PROVIDER_ID,
}
_KIND_LABELS: dict[LlmProviderKind, str] = {
    "ocr": "OCR",
    "ai": "AI 视觉转写",
    "assistant": "工作台 AI 助手",
}


def provider_profiles(kind: LlmProviderKind) -> tuple[LlmProviderProfile, ...]:
    return _PROFILES[kind]


def default_provider_id(kind: LlmProviderKind) -> str:
    return _DEFAULTS[kind]


def resolve_provider_profile(
    kind: LlmProviderKind,
    provider_id: str | None,
) -> LlmProviderProfile:
    resolved = (provider_id or _DEFAULTS[kind]).strip()
    for profile in _PROFILES[kind]:
        if profile.id == resolved:
            return profile
    available = ", ".join(profile.id for profile in _PROFILES[kind])
    raise ValueError(f"未知{_KIND_LABELS[kind]} provider：{resolved}。可选：{available}")


def resolve_provider_profile_or_default(
    kind: LlmProviderKind,
    provider_id: str | None,
) -> LlmProviderProfile:
    try:
        return resolve_provider_profile(kind, provider_id)
    except ValueError:
        return resolve_provider_profile(kind, _DEFAULTS[kind])
