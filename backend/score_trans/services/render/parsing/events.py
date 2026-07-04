from __future__ import annotations

from fractions import Fraction

from ....domain.jianpu_tokens import duration_affixes
from ....models.score import JianpuEvent, JianpuPitch


def _event_token(event: JianpuEvent) -> str:
    pitches = sorted(event.pitches, key=lambda pitch: pitch.rank, reverse=True)
    tokens = [_pitch_token(pitch) for pitch in pitches]
    prefix, suffix = duration_affixes(event.duration)
    if len(tokens) > 1:
        return prefix + "[" + "+".join(tokens) + "]" + suffix
    return prefix + tokens[0] + suffix if tokens else "?"


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
    prefix, suffix = duration_affixes(duration)
    return prefix + body + suffix


def _note_body_token(event: JianpuEvent) -> str:
    """Generate note token without duration prefix/suffix."""
    pitches = sorted(event.pitches, key=lambda pitch: pitch.rank, reverse=True)
    tokens = [_pitch_token(pitch) for pitch in pitches]
    if len(tokens) > 1:
        return "[" + "+".join(tokens) + "]"
    return tokens[0] if tokens else "?"
