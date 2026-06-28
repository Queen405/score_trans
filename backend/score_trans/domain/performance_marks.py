from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ..models.common.types import InstrumentProfile, normalize_instrument_profile
from ..models.score import Event


MarkCategory = Literal["articulation", "ornament", "technical", "spanner"]
MarkPlacement = Literal["above", "left", "right", "below-right"]
MarkTarget = Literal["pitched", "chord"]


@dataclass(frozen=True, slots=True)
class PerformanceMark:
    id: str
    token: str
    category: MarkCategory
    renderer: str
    labels: tuple[tuple[InstrumentProfile, str], ...]
    description: str
    profiles: tuple[InstrumentProfile, ...] = (
        "general",
        "erhu",
        "ruan",
        "guzheng",
    )
    aliases: tuple[str, ...] = ()
    musicxml_section: str | None = None
    musicxml_name: str | None = None
    custom_musicxml: str | None = None
    placement: MarkPlacement = "above"
    measure_scope: bool = False
    recommended_in_general: bool = True
    syntax: str | None = None
    visual_width: float = 18.0
    visual_height: float = 16.0
    stack_gap: float = 2.0
    target: MarkTarget = "pitched"

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
            ("ruan", "断音"),
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
            ("ruan", "轮指"),
            ("guzheng", "摇指"),
        ),
        "三条平行短斜线；名称由乐器模式决定。",
        profiles=("erhu", "ruan", "guzheng"),
        musicxml_section="ornaments",
        musicxml_name="tremolo",
        placement="below-right",
        measure_scope=True,
        recommended_in_general=False,
    ),
    PerformanceMark(
        "continuous-slide",
        "lh",
        "spanner",
        "directional-slide",
        (
            ("erhu", "连线滑音"),
            ("ruan", "滑音"),
            ("guzheng", "有时值滑音"),
        ),
        "连接前一个音和目标音；古筝模式根据两端音高决定上滑或下滑。",
        profiles=("erhu", "ruan", "guzheng"),
        musicxml_section="notations",
        musicxml_name="slide",
        recommended_in_general=False,
        syntax="3 ^lh 5",
        visual_width=36.0,
        visual_height=18.0,
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
        (
            ("erhu", "自然泛音"),
            ("ruan", "泛音"),
            ("guzheng", "泛音"),
        ),
        "小型空心正圆。",
        profiles=("erhu", "ruan", "guzheng"),
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
        (
            ("erhu", "上滑音"),
            ("guzheng", "上滑音"),
        ),
        "音符左侧的短上扬弧线。",
        profiles=("erhu", "guzheng"),
        musicxml_section="articulations",
        musicxml_name="scoop",
        placement="left",
    ),
    PerformanceMark(
        "plop",
        "xh",
        "technical",
        "plop",
        (
            ("erhu", "下滑音"),
            ("guzheng", "下滑音"),
        ),
        "音符左侧的短下落弧线。",
        profiles=("erhu", "guzheng"),
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
    PerformanceMark(
        "guzheng-sweep-tremolo",
        "sy",
        "technical",
        "guzheng-sweep-tremolo",
        (("guzheng", "扫摇"),),
        "中指扫弦并与大拇指摇指结合的成组短回钩符号。",
        profiles=("guzheng",),
        aliases=("guzheng:sweep-tremolo",),
        musicxml_section="technical",
        custom_musicxml="guzheng:sweep-tremolo",
        visual_width=24.0,
        visual_height=18.0,
    ),
    PerformanceMark(
        "string-sweep",
        "sx",
        "technical",
        "string-sweep",
        (
            ("ruan", "扫弦"),
            ("guzheng", "扫弦"),
        ),
        "带三条横档的斜向扫弦箭头。",
        profiles=("ruan", "guzheng"),
        aliases=(
            "guzheng-string-sweep",
            "guzheng:string-sweep",
            "ruan:string-sweep",
        ),
        musicxml_section="technical",
        custom_musicxml="score-trans:string-sweep",
        placement="right",
        visual_width=24.0,
        visual_height=24.0,
    ),
    PerformanceMark(
        "guzheng-double-tuo",
        "st",
        "technical",
        "guzheng-double-tuo",
        (("guzheng", "双托"),),
        "大拇指同时向外弹奏相邻两弦的双折钩符号。",
        profiles=("guzheng",),
        aliases=("guzheng:double-tuo",),
        musicxml_section="technical",
        custom_musicxml="guzheng:double-tuo",
        visual_width=22.0,
        target="chord",
    ),
    PerformanceMark(
        "guzheng-double-mo",
        "sm",
        "technical",
        "guzheng-double-mo",
        (("guzheng", "双抹"),),
        "食指同时向里弹奏相邻两弦的两条平行短斜线。",
        profiles=("guzheng",),
        aliases=("guzheng:double-mo",),
        musicxml_section="technical",
        custom_musicxml="guzheng:double-mo",
        target="chord",
    ),
    PerformanceMark(
        "arpeggio",
        "py",
        "technical",
        "arpeggio",
        (
            ("ruan", "琶音"),
            ("guzheng", "琶音"),
        ),
        "和弦左侧的竖向波浪线，表示各音按顺序弹奏。",
        profiles=("ruan", "guzheng"),
        aliases=("arpeggiate",),
        musicxml_section="notations",
        musicxml_name="arpeggiate",
        placement="left",
        visual_width=12.0,
        visual_height=30.0,
        target="chord",
    ),
    PerformanceMark(
        "ornament-note",
        "zy",
        "ornament",
        "ornament-note",
        (("ruan", "装饰音"),),
        "音符上方的小型装饰音符号，用于提示短小的旋律润饰。",
        profiles=("ruan",),
        aliases=("ruan:ornament-note",),
        musicxml_section="ornaments",
        custom_musicxml="ruan:ornament-note",
        visual_width=14.0,
        visual_height=20.0,
    ),
    PerformanceMark(
        "guzheng-board-front-flower",
        "bq",
        "technical",
        "guzheng-board-front-flower",
        (("guzheng", "花指板前花"),),
        "大拇指快速连续托弦且不另占时值的小花形符号。",
        profiles=("guzheng",),
        aliases=("guzheng:board-front-flower",),
        musicxml_section="technical",
        custom_musicxml="guzheng:board-front-flower",
        visual_height=20.0,
    ),
    PerformanceMark(
        "guzheng-on-beat-flower",
        "zb",
        "technical",
        "guzheng-on-beat-flower",
        (("guzheng", "花指正板花"),),
        "使用被标记音符时值的八向花形符号。",
        profiles=("guzheng",),
        aliases=("guzheng:on-beat-flower",),
        musicxml_section="technical",
        custom_musicxml="guzheng:on-beat-flower",
        visual_height=20.0,
    ),
    PerformanceMark(
        "guzheng-ascending-scrape",
        "sg",
        "technical",
        "guzheng-ascending-scrape",
        (("guzheng", "上行刮奏"),),
        "由低音向高音刮奏的右上方向箭头，标在音群起点。",
        profiles=("guzheng",),
        aliases=("guzheng:ascending-scrape",),
        musicxml_section="technical",
        custom_musicxml="guzheng:ascending-scrape",
        placement="right",
        visual_width=24.0,
        visual_height=22.0,
    ),
    PerformanceMark(
        "guzheng-descending-scrape",
        "xg",
        "technical",
        "guzheng-descending-scrape",
        (("guzheng", "下行刮奏"),),
        "由高音向低音刮奏的右下方向箭头，标在音群起点。",
        profiles=("guzheng",),
        aliases=("guzheng:descending-scrape",),
        musicxml_section="technical",
        custom_musicxml="guzheng:descending-scrape",
        placement="right",
        visual_width=24.0,
        visual_height=22.0,
    ),
    PerformanceMark(
        "guzheng-vibrato",
        "cy",
        "technical",
        "guzheng-vibrato",
        (("guzheng", "颤音"),),
        "左手轻颤琴弦的三段短波浪线，不使用 tr 字样。",
        profiles=("guzheng",),
        aliases=("guzheng:vibrato",),
        musicxml_section="technical",
        custom_musicxml="guzheng:vibrato",
        visual_width=24.0,
    ),
    PerformanceMark(
        "guzheng-ornament-up-slide",
        "zs",
        "technical",
        "guzheng-ornament-up-slide",
        (("guzheng", "装饰音上滑音"),),
        "先弹后按的紧凑上行折钩。",
        profiles=("guzheng",),
        aliases=("guzheng:ornament-up-slide",),
        musicxml_section="technical",
        custom_musicxml="guzheng:ornament-up-slide",
        placement="right",
    ),
    PerformanceMark(
        "guzheng-ornament-down-slide",
        "zx",
        "technical",
        "guzheng-ornament-down-slide",
        (("guzheng", "装饰音下滑音"),),
        "先按后弹的紧凑下行折钩。",
        profiles=("guzheng",),
        aliases=("guzheng:ornament-down-slide",),
        musicxml_section="technical",
        custom_musicxml="guzheng:ornament-down-slide",
        placement="right",
    ),
)


_BY_ID = {mark.id: mark for mark in PERFORMANCE_MARKS}
_BY_TOKEN = {mark.token: mark for mark in PERFORMANCE_MARKS}
if len(_BY_ID) != len(PERFORMANCE_MARKS):
    raise ValueError("演奏标记规范 ID 必须全局唯一")
if len(_BY_TOKEN) != len(PERFORMANCE_MARKS):
    raise ValueError("演奏标记文本 token 必须全局唯一")
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
                if mark.category == "spanner":
                    continue
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
    profile = normalize_instrument_profile(profile)
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
    profile = normalize_instrument_profile(profile)
    if profile == "general":
        return (
            "当前为普通识别模式。不要猜测二胡、阮、古筝等乐器专属技巧，"
            "只输出通用简谱标记。"
        )
    display_name = {
        "erhu": "二胡",
        "ruan": "阮",
        "guzheng": "古筝",
    }[profile]
    rows = [
        f"{mark.syntax or f'^{mark.token}'}={mark.label_for(profile)}"
        for mark in profile_marks(profile)
        if profile in mark.profiles and mark.token
    ]
    extra = "；".join(rows)
    range_rule = (
        "连线滑音写成“3 ^lh 5”，^lh 放在目标音前；整小节颤弓可在小节开头写 (^l)。"
        if profile == "erhu"
        else (
            "滑音写成“3 ^lh 5”，^lh 放在目标音前；"
            "琶音后必须是和弦；"
            "整小节轮指可在小节开头写 (^l)。"
            if profile == "ruan"
            else (
                "有时值滑音写成“3 ^lh 5”或“5 ^lh 3”，^lh 放在目标音前；"
                "双托、双抹和琶音后必须是和弦；"
                "上、下行刮奏只标记音群第一个音；"
                "整小节摇指可在小节开头写 (^l)。"
            )
        )
    )
    return (
        f"当前为{display_name}识别模式。识别图片中的演奏技巧并使用以下语法："
        f"{extra}。{range_rule}只使用目录中列出的技巧，不要输出长颤音波浪线。"
    )
