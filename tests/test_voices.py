"""复调（声部内多声线）检测纯函数测试。

判据：同一 staff、不同 voice、可见事件的时间区间重叠。
hidden（删除休止符）与 generated（补全休止符）不参与判定。
"""

from __future__ import annotations

from fractions import Fraction

from score_trans.domain.voices import (
    measure_is_polyphonic,
    measure_lanes,
    score_uses_lanes,
)
from score_trans.models.score import Event, JianpuPitch, JianpuScore, Measure


def _note(
    duration: Fraction,
    *,
    start: Fraction | None = None,
    voice: str | None = None,
    staff: str | None = None,
    degree: int = 1,
    hidden: bool = False,
    generated: bool = False,
) -> Event:
    return Event(
        kind="note",
        duration=duration,
        pitches=[JianpuPitch(degree)],
        start=start,
        voice=voice,
        staff=staff,
        hidden=hidden,
        generated=generated,
    )


def _rest(
    duration: Fraction,
    *,
    start: Fraction | None = None,
    voice: str | None = None,
    staff: str | None = None,
    hidden: bool = False,
    generated: bool = False,
) -> Event:
    return Event(
        kind="rest",
        duration=duration,
        start=start,
        voice=voice,
        staff=staff,
        hidden=hidden,
        generated=generated,
    )


def _measure(*events: Event) -> Measure:
    return Measure("1", duration=Fraction(4), events=list(events))


def test_overlapping_voices_are_polyphonic() -> None:
    # 用户场景：voice 1 休止+三个四分音符，voice 2 一个全音符并行
    measure = _measure(
        _rest(Fraction(1), start=Fraction(0), voice="1"),
        _note(Fraction(1), start=Fraction(1), voice="1"),
        _note(Fraction(1), start=Fraction(2), voice="1"),
        _note(Fraction(1), start=Fraction(3), voice="1"),
        _note(Fraction(4), start=Fraction(0), voice="2", degree=5),
    )
    assert measure_is_polyphonic(measure)


def test_sequential_pseudo_voices_are_not_polyphonic() -> None:
    # Audiveris 伪拆：voice 1 走前两拍，voice 2 从第三拍接续，互不重叠
    measure = _measure(
        _note(Fraction(1), start=Fraction(0), voice="1"),
        _note(Fraction(1), start=Fraction(1), voice="1"),
        _note(Fraction(1), start=Fraction(2), voice="2"),
        _note(Fraction(1), start=Fraction(3), voice="2"),
    )
    assert not measure_is_polyphonic(measure)


def test_touching_boundaries_are_not_overlap() -> None:
    # voice 1 [0,2)，voice 2 [2,4)：端点相接不算重叠
    measure = _measure(
        _note(Fraction(2), start=Fraction(0), voice="1"),
        _note(Fraction(2), start=Fraction(2), voice="2"),
    )
    assert not measure_is_polyphonic(measure)


def test_hidden_rests_do_not_trigger_polyphony() -> None:
    measure = _measure(
        _note(Fraction(4), start=Fraction(0), voice="1"),
        _rest(Fraction(4), start=Fraction(0), voice="2", hidden=True),
    )
    assert not measure_is_polyphonic(measure)


def test_generated_padding_rests_do_not_trigger_polyphony() -> None:
    measure = _measure(
        _note(Fraction(4), start=Fraction(0), voice="1"),
        _rest(Fraction(4), start=Fraction(0), voice="2", generated=True),
    )
    assert not measure_is_polyphonic(measure)


def test_visible_rest_lane_overlapping_notes_is_polyphonic() -> None:
    # voice 2 是一个可见的全休止符：谱面上必须显示，属于复调
    measure = _measure(
        _note(Fraction(1), start=Fraction(0), voice="1"),
        _note(Fraction(1), start=Fraction(1), voice="1"),
        _note(Fraction(1), start=Fraction(2), voice="1"),
        _note(Fraction(1), start=Fraction(3), voice="1"),
        _rest(Fraction(4), start=Fraction(0), voice="2"),
    )
    assert measure_is_polyphonic(measure)


def test_same_voice_chord_is_not_polyphonic() -> None:
    chord = Event(
        kind="note",
        duration=Fraction(4),
        pitches=[JianpuPitch(1), JianpuPitch(3), JianpuPitch(5)],
        start=Fraction(0),
        voice="1",
    )
    assert not measure_is_polyphonic(_measure(chord))


def test_different_staves_with_same_voice_number_are_not_polyphonic() -> None:
    measure = _measure(
        _note(Fraction(4), start=Fraction(0), voice="1", staff="1"),
        _note(Fraction(4), start=Fraction(0), voice="1", staff="2", degree=5),
    )
    assert not measure_is_polyphonic(measure)


def test_different_staves_are_parallel_not_polyphonic() -> None:
    # 大谱表两个 staff 各自单线并行：不是声部内复调
    measure = _measure(
        _note(Fraction(4), start=Fraction(0), voice="1", staff="1"),
        _note(Fraction(4), start=Fraction(0), voice="2", staff="2", degree=5),
    )
    assert not measure_is_polyphonic(measure)


def test_events_without_start_fall_back_to_sequential_cursor() -> None:
    # 文本解析来源的事件没有 start：按顺序游标处理，互不重叠
    measure = _measure(
        _note(Fraction(2), voice="1"),
        _note(Fraction(2), voice="2"),
    )
    assert not measure_is_polyphonic(measure)


def test_measure_lanes_ordering_and_grouping() -> None:
    measure = _measure(
        _note(Fraction(4), start=Fraction(0), voice="10", degree=3),
        _note(Fraction(4), start=Fraction(0), voice="2", degree=2),
        _note(Fraction(4), start=Fraction(0), voice=None, degree=1),
        _note(Fraction(4), start=Fraction(0), voice="solo", degree=4),
    )
    lanes = measure_lanes(measure)
    # voice 缺省归一为 "1"；数字 voice 升序，非数字最后
    assert [voice for _staff, voice in (key for key, _events in lanes)] == [
        "1",
        "2",
        "10",
        "solo",
    ]


def test_measure_lanes_skip_hidden_and_generated_events() -> None:
    measure = _measure(
        _note(Fraction(1), start=Fraction(0), voice="1"),
        _rest(Fraction(1), start=Fraction(1), voice="1", hidden=True),
        _rest(Fraction(2), start=Fraction(2), voice="1", generated=True),
    )
    lanes = measure_lanes(measure)
    assert len(lanes) == 1
    assert len(lanes[0][1]) == 1


def test_score_uses_lanes() -> None:
    plain = JianpuScore(
        measures=[_measure(_note(Fraction(4), start=Fraction(0), voice="1"))]
    )
    assert not score_uses_lanes(plain)
    poly = JianpuScore(
        measures=[
            _measure(_note(Fraction(4), start=Fraction(0), voice="1")),
            _measure(
                _note(Fraction(4), start=Fraction(0), voice="1"),
                _note(Fraction(4), start=Fraction(0), voice="2", degree=5),
            ),
        ]
    )
    assert score_uses_lanes(poly)
