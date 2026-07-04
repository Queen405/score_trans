from __future__ import annotations

from fractions import Fraction

from ....domain.jianpu_tokens import safe_duration_affixes
from ....models.score import JianpuEvent, JianpuPitch


def _event_token(event: JianpuEvent) -> str:
    if event.kind == "rest":
        body = "0"
    else:
        pitches = sorted(event.pitches, key=lambda pitch: pitch.rank, reverse=True)
        tokens = [_pitch_token(pitch) for pitch in pitches]
        body = (
            "[" + "+".join(tokens) + "]"
            if len(tokens) > 1
            else tokens[0]
            if tokens
            else "?"
        )
    prefix, suffix = safe_duration_affixes(_notated_duration(event))
    return prefix + body + suffix


def _notated_duration(event: JianpuEvent) -> Fraction:
    actual_count = event.tuplet_count
    if actual_count is None:
        return event.duration
    if actual_count <= 0:
        raise ValueError("连音组的实际音符数必须大于零")

    normal_count = event.tuplet_normal_count
    if normal_count is None:
        normal_count = 1
        while normal_count * 2 <= actual_count:
            normal_count *= 2
    if normal_count <= 0:
        raise ValueError("连音组的常规音符数必须大于零")
    return event.duration * Fraction(actual_count, normal_count)


def _pitch_token(pitch: JianpuPitch) -> str:
    accidental = pitch.accidental_text
    if accidental is None:
        accidental = {
            Fraction(-2, 1): "bb",
            Fraction(-3, 2): "tqf",
            Fraction(-1, 1): "b",
            Fraction(-1, 2): "qf",
            Fraction(0, 1): "",
            Fraction(1, 2): "qs",
            Fraction(1, 1): "#",
            Fraction(3, 2): "tqs",
            Fraction(2, 1): "x",
        }.get(
            pitch.accidental,
            "#" if pitch.accidental > 0 else "b" if pitch.accidental < 0 else "",
        )
    octave = "'" * max(0, pitch.octave) + "," * max(0, -pitch.octave)
    return f"{accidental}{pitch.degree}{octave}"


def _duration_token(body: str, duration: Fraction) -> str:
    prefix, suffix = safe_duration_affixes(duration)
    return prefix + body + suffix


def _note_body_token(event: JianpuEvent) -> str:
    """Generate note token without duration prefix/suffix."""
    pitches = sorted(event.pitches, key=lambda pitch: pitch.rank, reverse=True)
    tokens = [_pitch_token(pitch) for pitch in pitches]
    if len(tokens) > 1:
        return "[" + "+".join(tokens) + "]"
    return tokens[0] if tokens else "?"
