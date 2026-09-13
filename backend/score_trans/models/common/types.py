from __future__ import annotations

from typing import Literal, cast


AccidentalMode = Literal["auto", "sharp", "flat"]
MeasureNumberMode = Literal["all", "row_start", "none"]
# auto：检测到真实重叠时保留 voice；preserve：只要存在多个 voice 就保留；
# flatten：始终拍平为单线（旧行为）。
PolyphonyMode = Literal["auto", "preserve", "flatten"]


def normalize_polyphony_mode(mode: str) -> PolyphonyMode:
    if mode not in ("auto", "preserve", "flatten"):
        raise ValueError(f"不支持的复调模式：{mode}")
    return cast(PolyphonyMode, mode)


InstrumentProfile = Literal["general", "erhu", "ruan", "guzheng", "zhongruan"]
SUPPORTED_INSTRUMENT_PROFILES: tuple[InstrumentProfile, ...] = (
    "general",
    "erhu",
    "ruan",
    "guzheng",
)
ACCEPTED_INSTRUMENT_PROFILES: tuple[InstrumentProfile, ...] = (
    *SUPPORTED_INSTRUMENT_PROFILES,
    "zhongruan",
)


def normalize_instrument_profile(profile: str) -> InstrumentProfile:
    normalized = "ruan" if profile == "zhongruan" else profile
    if normalized not in SUPPORTED_INSTRUMENT_PROFILES:
        raise ValueError(f"不支持的乐器模式：{profile}")
    return cast(InstrumentProfile, normalized)


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

AutoKey = Literal["auto"]
TargetKeyOrAuto = TargetKey | AutoKey

IMAGE_SUFFIXES: frozenset[str] = frozenset(
    {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}
)
