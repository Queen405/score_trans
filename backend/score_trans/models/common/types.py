from __future__ import annotations

from typing import Literal


AccidentalMode = Literal["auto", "sharp", "flat"]
MeasureNumberMode = Literal["all", "row_start", "none"]
InstrumentProfile = Literal["general", "erhu", "zhongruan"]
TargetKey = Literal[
    "Cb",
    "Gb",
    "Db",
    "Ab",
    "Eb",
    "Bb",
    "F",
    "C",
    "G",
    "D",
    "A",
    "E",
    "B",
    "F#",
    "C#",
]

SUPPORTED_TARGET_KEYS: tuple[TargetKey, ...] = (
    "Cb",
    "Gb",
    "Db",
    "Ab",
    "Eb",
    "Bb",
    "F",
    "C",
    "G",
    "D",
    "A",
    "E",
    "B",
    "F#",
    "C#",
)

IMAGE_SUFFIXES: frozenset[str] = frozenset(
    {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}
)
