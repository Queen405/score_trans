from __future__ import annotations

from ....domain.jianpu import parse_jianpu_score
from ....domain.musicxml import score_to_jianpu_text


def validate_jianpu_text(
    text: str,
    *,
    title: str | None = None,
    normalize: bool = True,
) -> tuple[str, list[str]]:
    try:
        score = parse_jianpu_score(text, title=title)
    except ValueError as exc:
        return text, [str(exc)]

    validation_errors = [
        f"第 {index} 小节：{error}"
        for index, measure in enumerate(score.measures, start=1)
        for error in measure.validation_errors
    ]
    if not normalize:
        return text, validation_errors
    return score_to_jianpu_text(score), validation_errors
