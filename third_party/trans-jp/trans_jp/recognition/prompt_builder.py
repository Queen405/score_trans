from __future__ import annotations

from importlib import resources
from pathlib import Path
from typing import Any
import json
from ..models.candidates import CandidateRegistry

import yaml

_EXTERNAL_MERGE_KEYS = ("syntax_rules", "hard_constraints", "transcription_rules")


class PromptBuilder:
    def __init__(self, prompt_config_path: Path | None = None):
        self._config = _load_default_config()
        if prompt_config_path is not None:
            self._merge_external(Path(prompt_config_path))

    @property
    def system_message(self) -> str:
        return str(self._config.get("system_message") or "")

    def build_row_prompt(
        self,
        *,
        row_index: int,
        total_rows: int,
        target_key: str,
        title: str | None,
        extra_prompt: str | None,
    ) -> str:
        template = str(self._config.get("row_prompt_template") or "")
        title_hint = ""
        if title:
            title_hint = str(self._config.get("title_hint_template") or "").format(
                title=title
            )
        extra = ""
        if extra_prompt:
            extra = str(self._config.get("extra_prompt_template") or "").format(
                extra_prompt=extra_prompt
            )
        return template.format(
            row_index=row_index,
            total_rows=total_rows,
            target_key=target_key,
            title_hint=title_hint,
            extra_prompt=extra,
            syntax_rules=str(self._config.get("syntax_rules") or ""),
            row_transcription_rules=str(
                self._config.get("row_transcription_rules") or ""
            ),
            hard_constraints=str(self._config.get("hard_constraints") or ""),
            json_schema=str(self._config.get("json_schema") or ""),
        )

    def candidate_instructions(self, registry: CandidateRegistry) -> str:
        candidates = [
            {
                "id": c.candidate_id,
                "kind": c.kind,
                "bands": c.band_ids,
                "ambiguous": c.ambiguous,
            }
            for c in registry.candidates
        ]
        example = {
            "schema_version": 2,
            "row_type": "notation",
            "row_text": "3",
            "tokens": [{"text": "3", "role": "note", "candidate_ids": ["r0000:c0000"]}],
            "unresolved_candidates": [],
            "warnings": [],
        }
        return (
            "本次使用 schema_version=2。第一张图是原行，其余是候选图册。图册标签不是乐谱内容。"
            "只引用当前候选编号，禁止输出或猜测 x/w/y/h。普通音符一个编号；和弦按从高到低引用多个编号；小节线引用 barline 候选。"
            "找不到候选时 candidate_ids=[]，保留已看清的文本；看不清的候选放入 unresolved_candidates 并说明原因，绝不可代换成 0。"
            "不要因拍数修改音符。所有 token.text 仍须对应 row_text 的连续子串。候选可能是歌词或噪声，可不引用。"
            "返回格式示例："
            + json.dumps(example, ensure_ascii=False)
            + " 当前候选："
            + json.dumps(candidates, ensure_ascii=False)
        )

    def _merge_external(self, path: Path) -> None:
        if not path.is_file():
            raise FileNotFoundError(f"prompt 配置不存在: {path}")
        external = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(external, dict):
            return
        for key in _EXTERNAL_MERGE_KEYS:
            value = external.get(key)
            if isinstance(value, str) and value.strip():
                self._config[key] = value


def _load_default_config() -> dict[str, Any]:
    resource = resources.files("trans_jp").joinpath("config/prompt.yaml")
    with resource.open("r", encoding="utf-8") as fh:
        config = yaml.safe_load(fh)
    if not isinstance(config, dict):
        raise ValueError("内置 prompt.yaml 内容无效：顶层必须是 mapping")
    return config
