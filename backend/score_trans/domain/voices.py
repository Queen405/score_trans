"""声部内多声线（voice / lane）检测与分组。

MusicXML 解析会保留 ``Event.voice`` / ``Event.staff`` / ``Event.start``，
但 Audiveris 等 OMR 常把单旋律伪拆成多个 voice（时间上顺序拼接、互不
重叠）。本模块提供统一判据：**同一 staff、不同 voice、可见事件的时间
区间重叠** 才算真复调；``hidden``（删除休止符）与 ``generated``（补全
休止符）不参与判定。同一 voice 内的 chord 是单个多音 Event，天然不会
被误判为多声线。
"""

from __future__ import annotations

from fractions import Fraction

from ..models.score import Event, JianpuScore, Measure

# 声线键：(staff, voice)。voice 缺失时按 "1" 归一，与既有拍平逻辑一致。
LaneKey = tuple[str | None, str]


def lane_key(event: Event) -> LaneKey:
    voice = (event.voice or "1").strip()
    return (event.staff, voice or "1")


def _text_sort_key(value: str | None) -> tuple[int, int | str]:
    if value and value.isdigit():
        return (0, int(value))
    return (1, value or "")


def _lane_sort_key(key: LaneKey) -> tuple[tuple[int, int | str], tuple[int, int | str]]:
    staff, voice = key
    return (_text_sort_key(voice), _text_sort_key(staff))


def _is_lane_event(event: Event) -> bool:
    return event.kind in ("note", "rest") and not event.hidden and not event.generated


def _resolve_events(
    events: list[Event],
) -> list[tuple[int, Event, Fraction]]:
    """按文档顺序解析每个事件的起点；缺失 start 的事件沿用顺序游标。

    与 ``_normalize_measure`` 的游标语义一致：文本解析来源的事件（无 start）
    在文档顺序上天然首尾相接，跨 voice 不会因泳道分组而产生伪重叠。
    """
    resolved: list[tuple[int, Event, Fraction]] = []
    cursor = Fraction(0, 1)
    for index, event in enumerate(events):
        start = event.start if event.start is not None else cursor
        resolved.append((index, event, start))
        cursor = start + event.duration
    return resolved


def group_event_lanes(events: list[Event]) -> list[tuple[LaneKey, list[Event]]]:
    """按 (staff, voice) 分组可见事件，声线按 voice→staff 排序。"""
    groups: dict[LaneKey, list[tuple[Fraction, int, Event]]] = {}
    for index, event, start in _resolve_events(events):
        if not _is_lane_event(event):
            continue
        groups.setdefault(lane_key(event), []).append((start, index, event))
    lanes: list[tuple[LaneKey, list[Event]]] = []
    for key in sorted(groups, key=_lane_sort_key):
        ordered = [event for _start, _index, event in sorted(groups[key])]
        lanes.append((key, ordered))
    return lanes


def measure_lanes(measure: Measure) -> list[tuple[LaneKey, list[Event]]]:
    return group_event_lanes(measure.events)


def _lane_intervals(
    resolved: list[tuple[int, Event, Fraction]], key: LaneKey
) -> list[tuple[Fraction, Fraction]]:
    return [
        (start, start + event.duration)
        for _index, event, start in resolved
        if _is_lane_event(event) and lane_key(event) == key
    ]


def _intervals_overlap(
    a: list[tuple[Fraction, Fraction]], b: list[tuple[Fraction, Fraction]]
) -> bool:
    i = 0
    j = 0
    while i < len(a) and j < len(b):
        a_start, a_end = a[i]
        b_start, b_end = b[j]
        if a_start < b_end and b_start < a_end:
            return True
        if a_end <= b_end:
            i += 1
        else:
            j += 1
    return False


def events_are_polyphonic(events: list[Event]) -> bool:
    resolved = _resolve_events(events)
    keys = sorted(
        {
            lane_key(event)
            for _index, event, _start in resolved
            if _is_lane_event(event)
        },
        key=_lane_sort_key,
    )
    if len(keys) < 2:
        return False
    spans = [(key, _lane_intervals(resolved, key)) for key in keys]
    for i in range(len(spans)):
        for j in range(i + 1, len(spans)):
            (staff_a, voice_a), spans_a = spans[i]
            (staff_b, voice_b), spans_b = spans[j]
            if voice_a == voice_b or staff_a != staff_b:
                continue
            if _intervals_overlap(spans_a, spans_b):
                return True
    return False


def measure_is_polyphonic(measure: Measure) -> bool:
    return events_are_polyphonic(measure.events)


def score_uses_lanes(score: JianpuScore) -> bool:
    return any(measure_is_polyphonic(measure) for measure in score.measures)
