from __future__ import annotations

import json

from ....config import CONFIG_DIR
from ....models.common.errors import AITranscriptionError

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
    syntax_rules = _cfg_value(cfg, "syntax_rules")
    transcription_rules = cfg.get("transcription_rules", "")
    hard_constraints = cfg.get("hard_constraints", "")
    return (
        "你是 Score Trans 工作台里的简谱助手。你可以帮助用户解释、检查、修正、补全、"
        "重写本项目的简谱文本，也可以回答五线谱转简谱、MusicXML 与渲染相关的问题。\n\n"
        "每次回答都必须以本项目简谱语法为准。不要发明语法；不确定时请明确说明不确定点。"
        "当用户要求输出可粘贴到编辑器的简谱时，只输出符合语法的文本，避免把说明文字混入代码块内。\n\n"
        "【必须遵守的项目简谱语法】\n"
        f"{syntax_rules}\n\n"
        "【转写与校验要求】\n"
        f"{transcription_rules}\n\n"
        "【硬性约束】\n"
        f"{hard_constraints}\n\n"
        "回答风格：中文、简洁但要准确。发现用户给出的简谱有语法错误时，先指出问题，"
        "再给出可直接替换的修正版。特别注意和弦只能用 + 分隔，如 [1+3+5]；"
        "时值只能用 w/h/q/s/d 前缀和附点/延长线表示，不能使用 1/2、3/4 这类斜杠写法。"
        "如果需要展示核对过程，请用 <think>...</think> 包住简短、可审计的检查摘要；"
        "最终答案仍要放在 think 块外。"
    )
