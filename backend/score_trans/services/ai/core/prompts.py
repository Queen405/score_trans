from __future__ import annotations

from pathlib import Path

import yaml

from ....config import CONFIG_DIR
from ....models.common.errors import AITranscriptionError

_PROMPT_CONFIG: dict[str, str] | None = None


def _load_prompt_config() -> dict[str, str]:
    global _PROMPT_CONFIG
    if _PROMPT_CONFIG is not None:
        return _PROMPT_CONFIG
    config_path: Path = CONFIG_DIR / "ai_prompt.yaml"
    if config_path.is_file():
        with open(config_path, encoding="utf-8") as f:
            _PROMPT_CONFIG = yaml.safe_load(f)
    else:
        _PROMPT_CONFIG = {}
    return _PROMPT_CONFIG


def _cfg_value(cfg: dict[str, str], key: str) -> str:
    if key in cfg:
        return cfg[key]
    raise AITranscriptionError(
        f"ai_prompt.yaml 缺少必填字段 '{key}'。"
        f"请在 {CONFIG_DIR / 'ai_prompt.yaml'} 中配置。"
    )


def persisted_ai_settings() -> dict[str, str]:
    try:
        from score_trans.services.settings.settings_service import SettingsService

        return SettingsService().get_all()
    except Exception:
        return {}


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


def build_jianpu_assistant_system_prompt() -> str:
    cfg = _load_prompt_config()
    template = cfg.get(
        "assistant_prompt_template",
        "你是 Score Trans 工作台里的简谱助手。\n\n"
        "【必须遵守的项目简谱语法】\n{syntax_rules}\n\n"
        "【转写与校验要求】\n{transcription_rules}\n\n"
        "【硬性约束】\n{hard_constraints}",
    )
    syntax_rules = _cfg_value(cfg, "syntax_rules")
    transcription_rules = cfg.get("transcription_rules", "")
    hard_constraints = cfg.get("hard_constraints", "")
    return template.format(
        syntax_rules=syntax_rules,
        transcription_rules=transcription_rules,
        hard_constraints=hard_constraints,
    )
