from __future__ import annotations

import html
from pathlib import Path

from .parse.jianpu_text import parse_jianpu, parse_jianpu_score, parse_jianpu_scores
from .parse.musicxml import musicxml_to_scores
from .write.jianpu_text import scores_to_jianpu_text
from .write.musicxml import scores_to_musicxml
from .xml_utils import _read_musicxml
from ..models.common.types import AccidentalMode

__all__ = [
    "jianpu_file_to_musicxml",
    "jianpu_to_html",
    "jianpu_to_musicxml",
    "musicxml_file_to_jianpu",
    "musicxml_to_jianpu",
    "musicxml_to_jianpu_multi",
    "normalize_jianpu_text",
    "parse_jianpu",
    "parse_jianpu_score",
    "parse_jianpu_scores",
    "scores_to_jianpu_text",
]


def musicxml_file_to_jianpu(path: Path) -> str:
    return musicxml_to_jianpu(_read_musicxml(path))


def musicxml_to_jianpu(
    xml_text: str,
    *,
    accidental_mode: AccidentalMode = "auto",
) -> str:
    return musicxml_to_jianpu_multi(xml_text, accidental_mode=accidental_mode)


def musicxml_to_jianpu_multi(
    xml_text: str,
    *,
    accidental_mode: AccidentalMode = "auto",
) -> str:
    return scores_to_jianpu_text(
        musicxml_to_scores(xml_text), accidental_mode=accidental_mode
    )


def jianpu_file_to_musicxml(path: Path, title: str | None = None) -> str:
    return jianpu_to_musicxml(path.read_text(encoding="utf-8"), title=title)


def jianpu_to_musicxml(text: str, title: str | None = None) -> str:
    scores = parse_jianpu_scores(text, title=title)
    return scores_to_musicxml(scores, title=title)


def normalize_jianpu_text(
    text: str,
    *,
    title: str | None = None,
    accidental_mode: AccidentalMode = "auto",
) -> str:
    return scores_to_jianpu_text(
        parse_jianpu_scores(text, title=title),
        accidental_mode=accidental_mode,
    )


def jianpu_to_html(jianpu_text: str) -> str:
    body = html.escape(jianpu_text).replace("\n", "<br>")
    return f"<html><body><pre style='font-size:20px;line-height:1.8'>{body}</pre></body></html>"
