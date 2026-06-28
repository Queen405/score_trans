from __future__ import annotations

from ...domain.performance_marks import profile_marks
from ...models.common.types import (
    SUPPORTED_INSTRUMENT_PROFILES,
    InstrumentProfile,
)
from ...models.notation.schemas import (
    InstrumentProfileCatalog,
    PerformanceMarkCatalogItem,
    SyntaxExample,
)


_PROFILE_NAMES: dict[InstrumentProfile, str] = {
    "general": "普通",
    "erhu": "二胡",
    "ruan": "阮",
    "guzheng": "古筝",
    "zhongruan": "阮",
}

_RUAN_MARK_ORDER = (
    "tremolo",
    "string-sweep",
    "natural-harmonic",
    "continuous-slide",
    "ornament-note",
    "arpeggio",
)
_RUAN_MARK_INDEX = {
    mark_id: index for index, mark_id in enumerate(_RUAN_MARK_ORDER)
}

_GUZHENG_MARK_ORDER = (
    "tremolo",
    "guzheng-sweep-tremolo",
    "string-sweep",
    "natural-harmonic",
    "guzheng-double-tuo",
    "guzheng-double-mo",
    "arpeggio",
    "guzheng-board-front-flower",
    "guzheng-on-beat-flower",
    "guzheng-ascending-scrape",
    "guzheng-descending-scrape",
    "guzheng-vibrato",
    "scoop",
    "plop",
    "guzheng-ornament-up-slide",
    "guzheng-ornament-down-slide",
    "continuous-slide",
)
_GUZHENG_MARK_INDEX = {
    mark_id: index for index, mark_id in enumerate(_GUZHENG_MARK_ORDER)
}


class NotationActions:
    def list_instrument_profiles(self) -> list[InstrumentProfileCatalog]:
        return [
            self._profile_catalog(profile) for profile in SUPPORTED_INSTRUMENT_PROFILES
        ]

    def _profile_catalog(self, profile: InstrumentProfile) -> InstrumentProfileCatalog:
        marks = [
            PerformanceMarkCatalogItem(
                id="slur",
                syntax="(1 2)",
                name="连弓" if profile == "erhu" else "连音线",
                description=(
                    "同一弓内连奏多个音。"
                    if profile == "erhu"
                    else "用弧线连接需要圆滑演奏的音。"
                ),
                category="spanner",
                placement="above",
            )
        ]
        registered_marks = profile_marks(profile)
        if profile == "guzheng":
            registered_marks.sort(
                key=lambda mark: (
                    0 if "general" in mark.profiles else 1,
                    _GUZHENG_MARK_INDEX.get(mark.id, len(_GUZHENG_MARK_INDEX)),
                )
            )
        elif profile == "ruan":
            registered_marks.sort(
                key=lambda mark: (
                    0 if "general" in mark.profiles else 1,
                    _RUAN_MARK_INDEX.get(mark.id, len(_RUAN_MARK_INDEX)),
                )
            )
        marks.extend(
            PerformanceMarkCatalogItem(
                id=mark.id,
                syntax=mark.syntax or f"^{mark.token}",
                name=mark.label_for(profile),
                description=mark.description,
                category=mark.category,
                placement=mark.placement,
                target=mark.target,
            )
            for mark in registered_marks
        )
        ranges: list[SyntaxExample] = []
        combinations: list[SyntaxExample] = []
        if profile in {"erhu", "ruan", "guzheng"}:
            technique = {
                "erhu": "颤弓",
                "ruan": "轮指",
                "guzheng": "摇指",
            }[profile]
            ranges.append(
                SyntaxExample(
                    syntax="(^l) 1 2 3 4 |",
                    description=f"本小节所有音符和和弦使用{technique}，休止符除外。",
                )
            )
        if profile == "erhu":
            combinations.extend(
                [
                    SyntaxExample(
                        syntax="^. (1 ^. 2)",
                        description="连弓范围内的每个音都使用顿弓，即连顿弓。",
                    ),
                    SyntaxExample(
                        syntax="(3 ^lh 5)",
                        description="同一连弓内从 3 连线滑到 5。",
                    ),
                ]
            )
        if profile == "guzheng":
            combinations.extend(
                [
                    SyntaxExample(
                        syntax="3 ^lh 5 / 5 ^lh 3",
                        description="根据前后单音音高自动绘制有时值上滑音或下滑音。",
                    ),
                    SyntaxExample(
                        syntax="^st [3+5] / ^sm [1+2] / ^py [1+3+5]",
                        description="双托、双抹和琶音必须标记和弦。",
                    ),
                    SyntaxExample(
                        syntax="^sg 3 5 6 1 / ^xg 1 6 5 3",
                        description="上、下行刮奏标在音群第一个音上。",
                    ),
                ]
            )
        if profile == "ruan":
            combinations.extend(
                [
                    SyntaxExample(
                        syntax="3 ^lh 5",
                        description="从前一个音连续滑到目标音。",
                    ),
                    SyntaxExample(
                        syntax="^py [1+3+5]",
                        description="琶音必须标记和弦。",
                    ),
                ]
            )
        return InstrumentProfileCatalog(
            id=profile,
            name=_PROFILE_NAMES[profile],
            marks=marks,
            range_examples=ranges,
            combination_examples=combinations,
        )
