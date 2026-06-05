from __future__ import annotations

import re
from typing import Any

from score_trans.models.score import TextRole


def infer_text_role(text: str) -> TextRole:
    lowered = text.lower()
    if re.search(r"\b(allegro|andante|moderato|largo|adagio|presto|rit\.?|accel\.?)\b", lowered):
        return "expression"
    if re.search(r"\b\d+\s*=\s*[A-Ga-g]", text):
        return "expression"
    if re.fullmatch(r"\d+", text.strip()):
        return "measure_number"
    return "other"


def normalize_text_role(value: Any, text: str) -> TextRole:
    role = str(value or "").strip().lower().replace("-", "_")
    aliases = {
        "tempo": "expression",
        "dynamic": "expression",
        "dynamics": "expression",
        "expression_text": "expression",
        "bar_number": "measure_number",
        "measure": "measure_number",
        "measure_no": "measure_number",
        "measure_num": "measure_number",
        "lyrics": "lyric",
        "annotation": "other",
        "unknown": "other",
    }
    normalized = aliases.get(role, role)
    if normalized in TextRole.__args__:
        return normalized  # type: ignore[return-value]
    return infer_text_role(text)
