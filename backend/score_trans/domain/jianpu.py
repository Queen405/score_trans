from __future__ import annotations

import html
from pathlib import Path

from .parse.jianpu_text import parse_jianpu, parse_jianpu_score
from .parse.musicxml import musicxml_to_score
from .write.jianpu_text import score_to_jianpu_text
from .write.musicxml import score_to_musicxml
from .xml_utils import _read_musicxml

__all__ = [
    "jianpu_file_to_musicxml",
    "jianpu_to_html",
    "jianpu_to_musicxml",
    "musicxml_file_to_jianpu",
    "musicxml_to_jianpu",
    "normalize_jianpu_text",
    "parse_jianpu",
    "parse_jianpu_score",
]


def musicxml_file_to_jianpu(path: Path) -> str:
    return musicxml_to_jianpu(_read_musicxml(path))


def musicxml_to_jianpu(xml_text: str) -> str:
    return score_to_jianpu_text(musicxml_to_score(xml_text))


def jianpu_file_to_musicxml(path: Path, title: str = "Jianpu Import") -> str:
    return jianpu_to_musicxml(path.read_text(encoding="utf-8"), title=title)


def jianpu_to_musicxml(text: str, title: str = "Jianpu Import") -> str:
    score = parse_jianpu_score(text, title=title)
    return score_to_musicxml(score, title=title)


def normalize_jianpu_text(text: str, *, title: str | None = None) -> str:
    return score_to_jianpu_text(parse_jianpu_score(text, title=title))


def jianpu_to_html(jianpu_text: str) -> str:
    body = html.escape(jianpu_text).replace("\n", "<br>")
    return f"<html><body><pre style='font-size:20px;line-height:1.8'>{body}</pre></body></html>"
