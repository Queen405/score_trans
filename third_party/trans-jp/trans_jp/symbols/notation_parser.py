from __future__ import annotations
import re
from fractions import Fraction
from ..models.notation import Pitch, Notation

_PITCH = re.compile(r"(##|bb|[#bn♯♭♮]?)([0-7])([\x27,]*)")
_NOTE = re.compile(
    r"(w|h|q|s|d+)?(\[[^\]]+\]|(?:##|bb|[#bn♯♭♮]?)[0-7][\x27,]*)(\.*)(-*)"
)
_ACC = {"#": "♯", "b": "♭", "n": "♮", "##": "𝄪", "bb": "𝄫"}


def parse_notation(text: str) -> Notation | None:
    text = text.strip()
    if text in {"|", "||", "|||", "|:", ":|", ":|:"}:
        return Notation("barline")
    if text and set(text) == {"-"}:
        return Notation("extension", extensions=len(text), duration=Fraction(len(text)))
    if text and set(text) <= set("()~"):
        return Notation("relation", opens=text.count("("), closes=text.count(")"))
    lead = re.match(r"[()~]*", text).group()
    tail = re.search(r"[()~]*$", text).group()
    end = len(text) - len(tail) if tail else len(text)
    match = _NOTE.fullmatch(text[len(lead) : end])
    if not match:
        return None
    prefix, body, dots, dashes = match.groups()
    parts = body[1:-1].split("+") if body.startswith("[") else [body]
    pitches = []
    for part in parts:
        p = _PITCH.fullmatch(part)
        if p is None or (len(parts) > 1 and p[2] == "0"):
            return None
        pitches.append(
            Pitch(p[2], p[3].count("'") - p[3].count(","), _ACC.get(p[1], p[1]))
        )
    lines = {"q": 1, "s": 2}.get(
        prefix, len(prefix) + 2 if prefix and prefix.startswith("d") else 0
    )
    base = Fraction(1, 2**lines) if lines else Fraction({"w": 4, "h": 2}.get(prefix, 1))
    duration = base * (2 - Fraction(1, 2 ** len(dots))) + len(dashes)
    return Notation(
        "note",
        tuple(sorted(pitches, key=lambda p: p.order, reverse=True)),
        lines,
        len(dots),
        len(dashes) + {"w": 3, "h": 1}.get(prefix, 0),
        duration,
        lead.count("("),
        tail.count(")"),
        "~" in tail,
        "~" in lead,
    )
