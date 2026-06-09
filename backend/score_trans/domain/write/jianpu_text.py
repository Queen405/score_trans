from __future__ import annotations

from fractions import Fraction

from ..jianpu_tokens import duration_affixes
from ...models.score import Event, JianpuPitch, JianpuScore, TextBlock


def score_to_jianpu_text(score: JianpuScore) -> str:
    lines = [f"1={score.target_key}", f"{score.beats}/{score.beat_type}"]
    if score.title and score.title != "简谱":
        lines.insert(0, f"title={score.title}")
    measures = []
    lyrics: list[str] = []
    for measure in score.measures:
        events = measure.events
        tokens = []
        for event in events:
            if event.dynamic:
                tokens.append(f"\\{event.dynamic}")
            all_marks = list(event.articulations or (
                [event.articulation] if event.articulation else []
            ))
            all_marks.extend(event.ornaments or [])
            for mark in all_marks:
                token = _articulation_token(mark)
                if token:
                    tokens.append(f"^{token}")
            tokens.append(_event_to_token(event))
            if event.lyric:
                lyrics.append(event.lyric)
        prefix = "|: " if getattr(measure, "repeat_start", False) else ""
        repeat_count = getattr(measure, "repeat_count", 1)
        repeat_suffix = f" *{repeat_count}" if repeat_count > 1 else ""
        suffix = " :|" if getattr(measure, "repeat_end", False) else ""
        measures.append(prefix + " ".join(tokens) + repeat_suffix + suffix)
    for m in measures:
        lines.append(m + " |")
    if lyrics:
        lines.append(f"L: {' '.join(lyrics)}")
    text_lines = [_text_block_to_directive(block) for block in score.text_blocks if block.text.strip() and block.role != "instrument"]
    if text_lines:
        lines.append("")
        lines.extend(text_lines)
    return "\n".join(lines)


def _text_block_to_directive(block: TextBlock) -> str:
    text = " ".join(block.text.split())
    role = block.role or "other"
    if block.bbox is None:
        return f"@text - - - - {role} {text}"
    x1, y1, x2, y2 = block.bbox
    return f"@text {_fmt_num(x1)} {_fmt_num(y1)} {_fmt_num(x2)} {_fmt_num(y2)} {role} {text}"


def _fmt_num(value: float) -> str:
    return f"{value:.3f}".rstrip("0").rstrip(".")


def _event_to_token(event: Event) -> str:
    prefix, suffix = _duration_parts(event.duration)
    if event.kind == "rest":
        body = "0"
    else:
        tokens = [_pitch_to_token(pitch) for pitch in event.pitches]
        body = "[" + "+".join(tokens) + "]" if len(tokens) > 1 else tokens[0] if tokens else "?"
    body = prefix + body + suffix
    if event.tie_stop:
        body = "~" + body
    if event.slur_start:
        body = "(" + body
    if event.slur_stop:
        body = body + ")"
    if event.tie_start:
        body = body + "~"
    return body


def _duration_parts(duration: Fraction) -> tuple[str, str]:
    return duration_affixes(duration)


def _articulation_token(name: str) -> str | None:
    return {
        "accent": ">",
        "strong-accent": ">",
        "staccato": ".",
        "tenuto": "-",
        "trill-mark": "r",
        "fermata": "f",
        "tremolo": "l",
    }.get(name, name if name else None)


def _pitch_to_token(pitch: JianpuPitch) -> str:
    accidental = pitch.accidental_text
    if accidental is None:
        accidental = "#" if pitch.accidental > 0 else "b" if pitch.accidental < 0 else ""
    octave = "'" * max(0, pitch.octave) + "," * max(0, -pitch.octave)
    return f"{accidental}{pitch.degree}{octave}"


def _duration_suffix(duration: Fraction) -> str:
    if duration == Fraction(3, 2):
        return "."
    if duration == Fraction(3, 4):
        return "/."
    if duration == Fraction(3, 8):
        return "//."
    if duration >= 1:
        whole = int(duration)
        remain = duration - whole
        return "-" * max(0, whole - 1) + _duration_suffix(remain) if remain else "-" * max(0, whole - 1)
    if duration == Fraction(1, 2):
        return "/"
    if duration == Fraction(1, 4):
        return "//"
    if duration == Fraction(1, 8):
        return "///"
    return f"({duration})"
