from __future__ import annotations

from ...domain.performance_marks import profile_marks
from ...models.common.types import InstrumentProfile
from ...models.notation.schemas import (
    InstrumentProfileCatalog,
    PerformanceMarkCatalogItem,
    SyntaxExample,
)


_PROFILE_NAMES: dict[InstrumentProfile, str] = {
    "general": "普通",
    "erhu": "二胡",
    "zhongruan": "中阮",
}


class NotationActions:
    def list_instrument_profiles(self) -> list[InstrumentProfileCatalog]:
        return [
            self._profile_catalog(profile)
            for profile in ("general", "erhu", "zhongruan")
        ]

    def _profile_catalog(
        self, profile: InstrumentProfile
    ) -> InstrumentProfileCatalog:
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
        marks.extend(
            PerformanceMarkCatalogItem(
                id=mark.id,
                syntax=f"^{mark.token}",
                name=mark.label_for(profile),
                description=mark.description,
                category=mark.category,
                placement=mark.placement,
            )
            for mark in profile_marks(profile)
        )
        if profile == "erhu":
            marks.insert(
                next(
                    (
                        index
                        for index, mark in enumerate(marks)
                        if mark.id == "finger-pad-slide"
                    ),
                    len(marks),
                ),
                PerformanceMarkCatalogItem(
                    id="continuous-slide",
                    syntax="3 ^lh 5",
                    name="连线滑音",
                    description="从前一个音连续滑到标记后的目标音。",
                    category="spanner",
                    placement="between",
                ),
            )
        ranges: list[SyntaxExample] = []
        combinations: list[SyntaxExample] = []
        if profile in {"erhu", "zhongruan"}:
            technique = "颤弓" if profile == "erhu" else "轮指"
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
        return InstrumentProfileCatalog(
            id=profile,
            name=_PROFILE_NAMES[profile],
            marks=marks,
            range_examples=ranges,
            combination_examples=combinations,
        )
