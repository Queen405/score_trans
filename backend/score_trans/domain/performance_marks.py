from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ..models.common.types import InstrumentProfile
from ..models.score import Event


MarkCategory = Literal["articulation", "ornament", "technical"]
MarkPlacement = Literal["above", "left", "right", "below-right"]


@dataclass(frozen=True, slots=True)
class PerformanceMark:
    id: str
    token: str
    category: MarkCategory
    renderer: str
    labels: tuple[tuple[InstrumentProfile, str], ...]
    description: str
    profiles: tuple[InstrumentProfile, ...] = ("general", "erhu", "zhongruan")
    aliases: tuple[str, ...] = ()
    musicxml_section: str | None = None
    musicxml_name: str | None = None
    custom_musicxml: str | None = None
    placement: MarkPlacement = "above"
    measure_scope: bool = False
    recommended_in_general: bool = True

    def label_for(self, profile: InstrumentProfile) -> str:
        labels = dict(self.labels)
        return labels.get(profile) or labels.get("general") or self.id


PERFORMANCE_MARKS: tuple[PerformanceMark, ...] = (
    PerformanceMark(
        "accent",
        ">",
        "articulation",
        "accent",
        (("general", "重音"),),
        "强调当前音。",
        aliases=("strong-accent",),
        musicxml_section="articulations",
        musicxml_name="accent",
        measure_scope=True,
    ),
    PerformanceMark(
        "tenuto",
        "-",
        "articulation",
        "tenuto",
        (("general", "保持"),),
        "充分保持当前音的时值。",
        musicxml_section="articulations",
        musicxml_name="tenuto",
    ),
    PerformanceMark(
        "staccato",
        ".",
        "articulation",
        "staccato",
        (
            ("general", "断音"),
            ("erhu", "顿弓（跳弓）"),
            ("zhongruan", "断音"),
        ),
        "使用实心倒三角表示短促而有弹性的音。",
        musicxml_section="articulations",
        musicxml_name="staccato",
        measure_scope=True,
    ),
    PerformanceMark(
        "trill-mark",
        "r",
        "articulation",
        "trill",
        (("general", "颤音"),),
        "短颤音，只显示 tr，不绘制延长波浪线。",
        musicxml_section="ornaments",
        musicxml_name="trill-mark",
        measure_scope=True,
    ),
    PerformanceMark(
        "fermata",
        "f",
        "articulation",
        "fermata",
        (("general", "延音记号"),),
        "按音乐表现需要延长当前音。",
        musicxml_section="notations",
        musicxml_name="fermata",
        measure_scope=True,
    ),
    PerformanceMark(
        "tremolo",
        "l",
        "ornament",
        "three-slash",
        (
            ("erhu", "颤弓（抖弓）"),
            ("zhongruan", "轮指"),
        ),
        "三条平行短斜线；名称由乐器模式决定。",
        profiles=("erhu", "zhongruan"),
        musicxml_section="ornaments",
        musicxml_name="tremolo",
        placement="below-right",
        measure_scope=True,
        recommended_in_general=False,
    ),
    PerformanceMark(
        "down-bow",
        "lg",
        "technical",
        "down-bow",
        (("erhu", "拉弓（出弓）"),),
        "开口向下的 Π 形弓法符号。",
        profiles=("erhu",),
        musicxml_section="technical",
        musicxml_name="down-bow",
    ),
    PerformanceMark(
        "up-bow",
        "tg",
        "technical",
        "up-bow",
        (("erhu", "推弓（入弓）"),),
        "两条斜线组成的 V 形弓法符号。",
        profiles=("erhu",),
        musicxml_section="technical",
        musicxml_name="up-bow",
    ),
    PerformanceMark(
        "throw-bow",
        "pg",
        "technical",
        "throw-bow",
        (("erhu", "抛弓"),),
        "九形折钩符号。",
        profiles=("erhu",),
        aliases=("erhu:throw-bow",),
        musicxml_section="technical",
        custom_musicxml="erhu:throw-bow",
    ),
    *tuple(
        PerformanceMark(
            f"fingering-{number}",
            str(number),
            "technical",
            "fingering",
            (("erhu", f"{number} 指"),),
            f"使用第 {number} 指。",
            profiles=("erhu",),
            aliases=(str(number),),
            musicxml_section="technical",
            musicxml_name="fingering",
        )
        for number in range(1, 5)
    ),
    PerformanceMark(
        "natural-harmonic",
        "zr",
        "technical",
        "natural-harmonic",
        (("erhu", "自然泛音"),),
        "小型空心正圆。",
        profiles=("erhu",),
        aliases=("harmonic",),
        musicxml_section="technical",
        musicxml_name="harmonic",
    ),
    PerformanceMark(
        "artificial-harmonic",
        "rg",
        "technical",
        "artificial-harmonic",
        (("erhu", "人工泛音"),),
        "小型空心菱形。",
        profiles=("erhu",),
        musicxml_section="technical",
        musicxml_name="harmonic",
    ),
    PerformanceMark(
        "pluck",
        "bx",
        "technical",
        "pluck",
        (("erhu", "弹弦、拨弦"),),
        "等长横竖线组成的加号。",
        profiles=("erhu",),
        musicxml_section="technical",
        musicxml_name="pluck",
    ),
    PerformanceMark(
        "scoop",
        "sh",
        "technical",
        "scoop",
        (("erhu", "上滑音"),),
        "音符左侧的短上扬弧线。",
        profiles=("erhu",),
        musicxml_section="articulations",
        musicxml_name="scoop",
        placement="left",
    ),
    PerformanceMark(
        "plop",
        "xh",
        "technical",
        "plop",
        (("erhu", "下滑音"),),
        "音符左侧的短下落弧线。",
        profiles=("erhu",),
        musicxml_section="articulations",
        musicxml_name="plop",
        placement="left",
    ),
    PerformanceMark(
        "finger-pad-slide",
        "dh",
        "technical",
        "finger-pad-slide",
        (("erhu", "垫指滑音"),),
        "两至三条交叠短弧线。",
        profiles=("erhu",),
        aliases=("erhu:finger-pad-slide",),
        musicxml_section="technical",
        custom_musicxml="erhu:finger-pad-slide",
        placement="right",
    ),
    PerformanceMark(
        "doit",
        "ds",
        "technical",
        "doit",
        (("erhu", "大上滑音"),),
        "音符右侧的长上扬线。",
        profiles=("erhu",),
        musicxml_section="articulations",
        musicxml_name="doit",
        placement="right",
    ),
    PerformanceMark(
        "falloff",
        "dx",
        "technical",
        "falloff",
        (("erhu", "大下滑音"),),
        "音符右侧的长下落线。",
        profiles=("erhu",),
        musicxml_section="articulations",
        musicxml_name="falloff",
        placement="right",
    ),
    PerformanceMark(
        "lower-return-slide",
        "hx",
        "technical",
        "lower-return-slide",
        (("erhu", "下回转滑音"),),
        "下行后回钩的滑音路径。",
        profiles=("erhu",),
        aliases=("erhu:lower-return-slide",),
        musicxml_section="technical",
        custom_musicxml="erhu:lower-return-slide",
        placement="right",
    ),
    PerformanceMark(
        "upper-return-slide",
        "hs",
        "technical",
        "upper-return-slide",
        (("erhu", "上回转滑音"),),
        "上行后回钩的滑音路径。",
        profiles=("erhu",),
        aliases=("erhu:upper-return-slide",),
        musicxml_section="technical",
        custom_musicxml="erhu:upper-return-slide",
        placement="right",
    ),
    PerformanceMark(
        "upper-trill",
        "sc",
        "ornament",
        "upper-trill",
        (("erhu", "上颤音"),),
        "短上邻音波形，不带延长线。",
        profiles=("erhu",),
        aliases=("inverted-mordent",),
        musicxml_section="ornaments",
        musicxml_name="inverted-mordent",
    ),
    PerformanceMark(
        "lower-trill",
        "xc",
        "ornament",
        "lower-trill",
        (("erhu", "下颤音"),),
        "带向下折点的短波形。",
        profiles=("erhu",),
        aliases=("mordent",),
        musicxml_section="ornaments",
        musicxml_name="mordent",
    ),
    PerformanceMark(
        "open-string",
        "kx",
        "technical",
        "open-string",
        (("erhu", "空弦"),),
        "字体数字 0，与自然泛音正圆区分。",
        profiles=("erhu",),
        musicxml_section="technical",
        musicxml_name="open-string",
    ),
    PerformanceMark(
        "inner-string",
        "nx",
        "technical",
        "inner-string",
        (("erhu", "内弦"),),
        "音符上方显示“内”。",
        profiles=("erhu",),
        aliases=("erhu:inner-string",),
        musicxml_section="technical",
        custom_musicxml="erhu:inner-string",
    ),
    PerformanceMark(
        "outer-string",
        "wx",
        "technical",
        "outer-string",
        (("erhu", "外弦"),),
        "音符上方显示“外”。",
        profiles=("erhu",),
        aliases=("erhu:outer-string",),
        musicxml_section="technical",
        custom_musicxml="erhu:outer-string",
    ),
    PerformanceMark(
        "breath-mark",
        "jx",
        "articulation",
        "breath-mark",
        (("erhu", "间歇记号"),),
        "逗号形的短暂停顿符号。",
        profiles=("erhu",),
        musicxml_section="articulations",
        musicxml_name="breath-mark",
    ),
    PerformanceMark(
        "hook-string",
        "gx",
        "technical",
        "hook-string",
        (("erhu", "勾弦"),),
        "短竖线加回钩。",
        profiles=("erhu",),
        aliases=("erhu:hook-string",),
        musicxml_section="technical",
        custom_musicxml="erhu:hook-string",
    ),
)


_BY_ID = {mark.id: mark for mark in PERFORMANCE_MARKS}
_BY_TOKEN = {mark.token: mark for mark in PERFORMANCE_MARKS}
_BY_ALIAS = {
    alias.strip().lower().replace("_", "-").replace(" ", "-"): mark
    for mark in PERFORMANCE_MARKS
    for alias in (mark.id, *mark.aliases)
}


def get_performance_mark(mark_id: str) -> PerformanceMark | None:
    return _BY_ID.get(mark_id)


def mark_for_token(token: str) -> PerformanceMark | None:
    return _BY_TOKEN.get(token.strip())


def canonical_mark_id(name: str) -> str | None:
    normalized = name.strip().lower().replace("_", "-").replace(" ", "-")
    mark = _BY_ALIAS.get(normalized)
    return mark.id if mark else None


def mark_token(name: str) -> str | None:
    mark_id = canonical_mark_id(name)
    mark = _BY_ID.get(mark_id or "")
    return mark.token if mark else None


def normalize_event_marks(event: Event) -> None:
    source_groups: tuple[tuple[MarkCategory, list[str]], ...] = (
        (
            "articulation",
            [
                *event.articulations,
                *([event.articulation] if event.articulation else []),
            ],
        ),
        ("ornament", list(event.ornaments)),
        ("technical", list(event.technical)),
    )
    categorized: dict[MarkCategory, list[str]] = {
        "articulation": [],
        "ornament": [],
        "technical": [],
    }
    seen: set[str] = set()
    for source_category, group in source_groups:
        for raw in group:
            mark_id = canonical_mark_id(raw)
            if mark_id is not None:
                if mark_id in seen:
                    continue
                mark = _BY_ID[mark_id]
                categorized[mark.category].append(mark.id)
                seen.add(mark.id)
                continue
            unknown_key = f"{source_category}:{raw}"
            if unknown_key in seen:
                continue
            categorized[source_category].append(raw)
            seen.add(unknown_key)
    event.articulations = categorized["articulation"]
    event.articulation = event.articulations[0] if event.articulations else None
    event.ornaments = categorized["ornament"]
    event.technical = categorized["technical"]


def event_mark_ids(
    articulations: list[str],
    ornaments: list[str],
    technical: list[str],
) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in (*articulations, *ornaments, *technical):
        mark_id = canonical_mark_id(raw)
        if mark_id and mark_id not in seen:
            result.append(mark_id)
            seen.add(mark_id)
    return result


def profile_marks(profile: InstrumentProfile) -> list[PerformanceMark]:
    marks: list[PerformanceMark] = []
    for mark in PERFORMANCE_MARKS:
        if profile == "general":
            if "general" not in mark.profiles or not mark.recommended_in_general:
                continue
        elif profile not in mark.profiles and "general" not in mark.profiles:
            continue
        marks.append(mark)
    return marks


def instrument_prompt(profile: InstrumentProfile) -> str:
    if profile == "general":
        return (
            "当前为普通识别模式。不要猜测二胡、中阮等乐器专属技巧，"
            "只输出通用简谱标记。"
        )
    display_name = "二胡" if profile == "erhu" else "中阮"
    rows = [
        f"^{mark.token}={mark.label_for(profile)}"
        for mark in profile_marks(profile)
        if profile in mark.profiles and mark.token
    ]
    extra = "；".join(rows)
    range_rule = (
        "连线滑音写成“3 ^lh 5”，^lh 放在目标音前；"
        "整小节颤弓可在小节开头写 (^l)。"
        if profile == "erhu"
        else "整小节轮指可在小节开头写 (^l)。"
    )
    return (
        f"当前为{display_name}识别模式。识别图片中的演奏技巧并使用以下语法："
        f"{extra}。{range_rule}不要输出长颤音波浪线。"
    )
