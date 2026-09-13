"""多声部往返不变量测试。

守护这条链路：MusicXML → 简谱文本 → MusicXML。

背景见 docs/multi-part-audit-2026-09.md。该文档记录了多声部功能的问题清单，
其中 P0 级别的缺陷（voice 塌缩、低音谱号丢失、声部名丢失）正是被本文件
标记为 xfail 的用例。

xfail(strict=True) 的意义：
  - 缺陷未修复时，用例失败 → 计为 xfail，CI 保持绿色；
  - 缺陷修复后，用例通过 → 计为 XPASS，strict 模式让 CI 报错，
    强制回来删掉 xfail 标记，避免"修好了却没人知道"。
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from fractions import Fraction

import pytest

from score_trans.domain.parse.jianpu_text import parse_jianpu_parts
from score_trans.domain.parse.musicxml import musicxml_to_scores
from score_trans.domain.write.jianpu_text import scores_to_jianpu_document
from score_trans.domain.write.musicxml import scores_to_musicxml

# --------------------------------------------------------------------------
# 测试用 MusicXML
# --------------------------------------------------------------------------

# 两个独立 part、各一个 voice（合唱形态，最常见的多声部场景）
TWO_PARTS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<score-partwise version="4.0">
  <part-list>
    <score-part id="P1"><part-name>高声部</part-name></score-part>
    <score-part id="P2"><part-name>低声部</part-name></score-part>
  </part-list>
  <part id="P1">
    <measure number="1">
      <attributes>
        <divisions>4</divisions>
        <key><fifths>0</fifths></key>
        <time><beats>4</beats><beat-type>4</beat-type></time>
        <clef><sign>G</sign><line>2</line></clef>
      </attributes>
      <note><pitch><step>C</step><octave>4</octave></pitch><duration>16</duration><voice>1</voice><type>whole</type></note>
    </measure>
  </part>
  <part id="P2">
    <measure number="1">
      <attributes><divisions>4</divisions></attributes>
      <note><pitch><step>C</step><octave>3</octave></pitch><duration>16</duration><voice>1</voice><type>whole</type></note>
    </measure>
  </part>
</score-partwise>
"""

# 单个 part 内含两个 voice（复调：voice 1 走 1-3，voice 2 同时奏 5）
TWO_VOICES_XML = """<?xml version="1.0" encoding="UTF-8"?>
<score-partwise version="4.0">
  <part-list>
    <score-part id="P1"><part-name>Flute</part-name></score-part>
  </part-list>
  <part id="P1">
    <measure number="1">
      <attributes>
        <divisions>4</divisions>
        <key><fifths>0</fifths></key>
        <time><beats>4</beats><beat-type>4</beat-type></time>
        <clef><sign>G</sign><line>2</line></clef>
      </attributes>
      <note><pitch><step>C</step><octave>4</octave></pitch><duration>8</duration><voice>1</voice><type>half</type></note>
      <note><pitch><step>E</step><octave>4</octave></pitch><duration>8</duration><voice>1</voice><type>half</type></note>
      <backup><duration>16</duration></backup>
      <note><pitch><step>G</step><octave>4</octave></pitch><duration>16</duration><voice>2</voice><type>whole</type></note>
    </measure>
  </part>
</score-partwise>
"""

# 单个 part 内含两个 voice 但时间不重叠（OMR 伪 voice：voice1 奏 C4 一半，voice2 接着奏 E4 一半）
SEQUENTIAL_VOICES_XML = """<?xml version="1.0" encoding="UTF-8"?>
<score-partwise version="4.0">
  <part-list>
    <score-part id="P1"><part-name>Voice</part-name></score-part>
  </part-list>
  <part id="P1">
    <measure number="1">
      <attributes>
        <divisions>4</divisions>
        <key><fifths>0</fifths></key>
        <time><beats>4</beats><beat-type>4</beat-type></time>
        <clef><sign>G</sign><line>2</line></clef>
      </attributes>
      <note><pitch><step>C</step><octave>4</octave></pitch><duration>8</duration><voice>1</voice><type>half</type></note>
      <note><pitch><step>E</step><octave>4</octave></pitch><duration>8</duration><voice>2</voice><type>half</type></note>
    </measure>
  </part>
</score-partwise>
"""

# 钢琴大谱表：一个 part、两个 staff、高音谱号 + 低音谱号
GRAND_STAFF_XML = """<?xml version="1.0" encoding="UTF-8"?>
<score-partwise version="4.0">
  <part-list>
    <score-part id="P1"><part-name>Piano</part-name></score-part>
  </part-list>
  <part id="P1">
    <measure number="1">
      <attributes>
        <divisions>4</divisions>
        <key><fifths>0</fifths></key>
        <time><beats>4</beats><beat-type>4</beat-type></time>
        <staves>2</staves>
        <clef number="1"><sign>G</sign><line>2</line></clef>
        <clef number="2"><sign>F</sign><line>4</line></clef>
      </attributes>
      <note><pitch><step>C</step><octave>4</octave></pitch><duration>16</duration><voice>1</voice><staff>1</staff><type>whole</type></note>
      <backup><duration>16</duration></backup>
      <note><pitch><step>C</step><octave>2</octave></pitch><duration>16</duration><voice>2</voice><staff>2</staff><type>whole</type></note>
    </measure>
  </part>
</score-partwise>
"""

# 单声部（用于验证声部名在退化场景下是否被保留）
SINGLE_PART_XML = """<?xml version="1.0" encoding="UTF-8"?>
<score-partwise version="4.0">
  <part-list>
    <score-part id="P1"><part-name>主旋律</part-name></score-part>
  </part-list>
  <part id="P1">
    <measure number="1">
      <attributes>
        <divisions>4</divisions>
        <key><fifths>0</fifths></key>
        <time><beats>4</beats><beat-type>4</beat-type></time>
        <clef><sign>G</sign><line>2</line></clef>
      </attributes>
      <note><pitch><step>C</step><octave>4</octave></pitch><duration>16</duration><voice>1</voice><type>whole</type></note>
    </measure>
  </part>
</score-partwise>
"""

# 用户报告场景：单声部某小节内两条并行线——
# voice 1 = 四分休止 + 三个带跳音的四分和弦，voice 2 = 一个全音符（低音）
POLYPHONIC_MEASURE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<score-partwise version="4.0">
  <part-list>
    <score-part id="P1"><part-name>Piano RH</part-name></score-part>
  </part-list>
  <part id="P1">
    <measure number="1">
      <attributes>
        <divisions>4</divisions>
        <key><fifths>0</fifths></key>
        <time><beats>4</beats><beat-type>4</beat-type></time>
        <clef><sign>G</sign><line>2</line></clef>
      </attributes>
      <note><rest/><duration>4</duration><voice>1</voice><type>quarter</type></note>
      <note><pitch><step>C</step><octave>4</octave></pitch><duration>4</duration><voice>1</voice><type>quarter</type>
        <notations><articulations><staccato/></articulations></notations></note>
      <note><chord/><pitch><step>E</step><octave>4</octave></pitch><duration>4</duration><voice>1</voice><type>quarter</type></note>
      <note><pitch><step>C</step><octave>4</octave></pitch><duration>4</duration><voice>1</voice><type>quarter</type>
        <notations><articulations><staccato/></articulations></notations></note>
      <note><chord/><pitch><step>E</step><octave>4</octave></pitch><duration>4</duration><voice>1</voice><type>quarter</type></note>
      <note><pitch><step>C</step><octave>4</octave></pitch><duration>4</duration><voice>1</voice><type>quarter</type>
        <notations><articulations><staccato/></articulations></notations></note>
      <note><chord/><pitch><step>E</step><octave>4</octave></pitch><duration>4</duration><voice>1</voice><type>quarter</type></note>
      <backup><duration>16</duration></backup>
      <note><pitch><step>C</step><octave>3</octave></pitch><duration>16</duration><voice>2</voice><type>whole</type></note>
    </measure>
    <measure number="2">
      <note><pitch><step>G</step><octave>4</octave></pitch><duration>16</duration><voice>1</voice><type>whole</type></note>
    </measure>
  </part>
</score-partwise>
"""

AUDIT_DOC = "docs/multi-part-audit-2026-09.md"


# --------------------------------------------------------------------------
# 辅助函数
# --------------------------------------------------------------------------


def _roundtrip(xml: str) -> tuple[list, list, str]:
    """MusicXML → 简谱文本 → 模型 → MusicXML，返回三阶段产物。"""
    original = musicxml_to_scores(xml)
    document = scores_to_jianpu_document(original)
    restored = [part.score for part in parse_jianpu_parts(document.text)]
    return original, restored, scores_to_musicxml(restored)


def _pitches_by_part(scores: list) -> list[list[tuple[int, int]]]:
    """按声部取音高序列。

    用 (degree, octave) 而不是 step：简谱是相对音高，未经转调时 step 为 None。
    """
    return [
        [
            (pitch.degree, pitch.octave)
            for measure in score.measures
            for event in measure.events
            for pitch in event.pitches
        ]
        for score in scores
    ]


def _measure_span(scores: list) -> Fraction:
    """所有声部中最晚的结束时刻，即音乐的时长。

    复调塌缩会让并行的音符变成串行，这个数值随之膨胀，
    因此它是捕获 voice 丢失最敏感的不变量。
    """
    return max(
        (
            event.start + event.duration
            for score in scores
            for measure in score.measures
            for event in measure.events
        ),
        default=Fraction(0),
    )


# --------------------------------------------------------------------------
# 当前成立的不变量 —— 回归守护，失败即代表功能被改坏
# --------------------------------------------------------------------------


def test_two_parts_keep_part_count_and_names_through_jianpu_text() -> None:
    """合唱形态：声部数量与声部名在往返后应保持一致。"""
    original, restored, _ = _roundtrip(TWO_PARTS_XML)

    assert len(restored) == len(original) == 2
    assert [s.part_name for s in restored] == ["高声部", "低声部"]


def test_two_parts_keep_pitches_and_measure_count() -> None:
    """合唱形态：音高序列、小节数、音乐时长都应保持不变。"""
    original, restored, _ = _roundtrip(TWO_PARTS_XML)

    assert (
        _pitches_by_part(restored)
        == _pitches_by_part(original)
        == [[(1, 0)], [(1, -1)]]
    )
    assert [len(s.measures) for s in restored] == [1, 1]
    assert _measure_span(restored) == _measure_span(original) == Fraction(4)


def test_two_parts_roundtrip_writes_both_parts_back_to_musicxml() -> None:
    """合唱形态：回写的 MusicXML 应保留两个声部及其名称。"""
    _, _, xml = _roundtrip(TWO_PARTS_XML)
    root = ET.fromstring(xml)

    assert root.findall(".//part") is not None
    assert len(root.findall(".//part")) == 2
    assert re.findall(r"<part-name>(.*?)</part-name>", xml) == ["高声部", "低声部"]


def test_grand_staff_splits_into_two_parts_with_distinct_pitches() -> None:
    """大谱表：应拆成两个声部，且保留各自音高（右手 C4、左手 C2）。"""
    original, restored, _ = _roundtrip(GRAND_STAFF_XML)

    assert len(restored) == 2
    assert (
        _pitches_by_part(restored)
        == _pitches_by_part(original)
        == [[(1, 0)], [(1, -2)]]
    )


def test_polyphonic_score_is_flattened_not_rejected() -> None:
    """flatten 模式：多 voice 声部拍平为单声部输出（旧行为），不硬拦截。"""
    scores = musicxml_to_scores(TWO_VOICES_XML)
    document = scores_to_jianpu_document(scores, polyphony_mode="flatten")
    assert document.text


def test_polyphonic_score_auto_mode_uses_voice_lanes() -> None:
    """auto 模式：真复调（时间重叠的多 voice）以 & 声线分隔输出，不拍平。"""
    scores = musicxml_to_scores(TWO_VOICES_XML)
    document = scores_to_jianpu_document(scores, polyphony_mode="auto")
    assert "h1 h3 & w5 |" in document.text


def test_polyphonic_score_preserve_mode_uses_voice_lanes() -> None:
    """preserve 模式：只要存在多个 voice 就按声线输出。"""
    scores = musicxml_to_scores(TWO_VOICES_XML)
    document = scores_to_jianpu_document(scores, polyphony_mode="preserve")
    assert "h1 h3 & w5 |" in document.text


# --------------------------------------------------------------------------
# flatten 模式：同声部多 voice 拍平为单声部输出 + 警告（旧可用行为，
# 供明确不需要复调的场景使用）；auto 模式下顺序伪 voice 仍合并、真复调
# 以 & 声线分隔无损输出。
# --------------------------------------------------------------------------


def test_polyphonic_score_flattens_to_single_part() -> None:
    """flatten 模式拍平后仍为单个声部文本。"""
    scores = musicxml_to_scores(TWO_VOICES_XML)
    document = scores_to_jianpu_document(scores, polyphony_mode="flatten")
    restored = [part.score for part in parse_jianpu_parts(document.text)]
    assert len(restored) == 1


def test_polyphonic_flatten_warns_with_part_name(caplog) -> None:
    """flatten 模式拍平时应通过警告日志提示风险，且包含声部名便于定位。"""
    import logging

    scores = musicxml_to_scores(TWO_VOICES_XML)
    with caplog.at_level(
        logging.WARNING, logger="score_trans.domain.write.jianpu_text"
    ):
        scores_to_jianpu_document(scores, polyphony_mode="flatten")
    assert any("Flute" in record.message for record in caplog.records)


def test_single_voice_score_does_not_raise() -> None:
    """单 voice 声部不受多 voice 警告路径影响。"""
    scores = musicxml_to_scores(TWO_PARTS_XML)
    # 不应抛错
    scores_to_jianpu_document(scores)


def test_sequential_voices_are_merged_not_rejected() -> None:
    """OMR 伪 voice：时间不重叠的多 voice 在 auto 模式下仍合并为单线。

    Audiveris 常把单声部旋律伪拆成多个 voice（甚至用 ``<backup>`` 造成时间
    重叠）；顺序拼接的伪 voice 合并为单声部文本，真复调才走 & 声线。
    """
    scores = musicxml_to_scores(SEQUENTIAL_VOICES_XML)
    document = scores_to_jianpu_document(scores)

    assert "&" not in document.text
    restored = [part.score for part in parse_jianpu_parts(document.text)]
    assert len(restored) == 1
    pitches = [
        (pitch.degree, pitch.octave)
        for measure in restored[0].measures
        for event in measure.events
        for pitch in event.pitches
    ]
    assert pitches == [(1, 0), (3, 0)]


# --------------------------------------------------------------------------
# 复调 voice 无损往返（& 声线语法）：fix-plan F2 的完整支持方案
# --------------------------------------------------------------------------


def test_polyphonic_measure_span_does_not_grow() -> None:
    """复调小节经文本往返后总时长不膨胀（4 拍不变 8 拍）。"""
    original, restored, _ = _roundtrip(TWO_VOICES_XML)
    assert _measure_span(restored) == _measure_span(original) == Fraction(4)


def test_polyphonic_note_start_positions_survive_roundtrip() -> None:
    """每个音符的 (voice, start) 在文本往返后保持不变。"""
    original, restored, _ = _roundtrip(TWO_VOICES_XML)

    def voice_starts(scores: list) -> set[tuple[str, Fraction]]:
        return {
            (event.voice or "1", event.start)
            for measure in scores[0].measures
            for event in measure.events
            if event.kind == "note"
        }

    assert voice_starts(restored) == voice_starts(original)


def test_voice_assignment_survives_jianpu_text_roundtrip() -> None:
    """文本解析恢复 voice 归属：voice 1 两个二分音符，voice 2 一个全音符。"""
    _original, restored, _ = _roundtrip(TWO_VOICES_XML)
    events = [event for event in restored[0].measures[0].events if event.kind == "note"]
    by_voice: dict[str, list[Fraction]] = {}
    for event in events:
        by_voice.setdefault(event.voice or "", []).append(event.duration)
    assert by_voice == {"1": [Fraction(2), Fraction(2)], "2": [Fraction(4)]}


def test_polyphonic_musicxml_output_keeps_voice_elements() -> None:
    """文本往返后回写 MusicXML：仍输出 <voice> 与 <backup>，不错拍。"""
    _, _, xml = _roundtrip(TWO_VOICES_XML)
    assert "<voice>2</voice>" in xml
    assert "<backup>" in xml


def test_user_reported_measure_uses_two_lanes() -> None:
    """用户场景：休止+跳音和弦线与全音符线并行，文本以 & 分隔、其余小节不变。"""
    scores = musicxml_to_scores(POLYPHONIC_MEASURE_XML)
    document = scores_to_jianpu_document(scores)

    lines = document.text.splitlines()
    lane_lines = [line for line in lines if "&" in line]
    assert len(lane_lines) == 1
    lane1, lane2 = (part.strip() for part in lane_lines[0].rstrip("|").split("&"))
    assert lane1.startswith("0")
    assert lane1.count("[") == 3
    assert lane1.count("^.") == 3
    assert lane2 == "w1,"
    # 相邻的单线小节保持原样，不带 &、不填充休止符
    assert "w5 |" in lines

    # 往返后两小节的跨度与原谱一致
    _original, restored, _ = _roundtrip(POLYPHONIC_MEASURE_XML)
    assert [m.span_duration for m in restored[0].measures] == [
        Fraction(4),
        Fraction(4),
    ]


def test_grand_staff_output_keeps_bass_clef() -> None:
    """大谱表：直接回写 MusicXML（不经简谱文本中转）应保留低音谱号。

    经简谱文本中转的谱号保留属于第二阶段（需扩展语法携带 clef），
    见 docs/multi-part-fix-plan.md F3。
    """
    scores = musicxml_to_scores(GRAND_STAFF_XML)
    xml = scores_to_musicxml(scores)

    assert "F" in re.findall(r"<sign>(.)</sign>", xml)


@pytest.mark.xfail(
    strict=True,
    reason=f"P0-2 大谱表结构丢失：从不输出 <staves>，两个 staff 变成两个独立分谱。见 {AUDIT_DOC}",
)
def test_grand_staff_output_keeps_staves_element() -> None:
    """大谱表：回写后仍应声明 staves 数量。"""
    _, _, xml = _roundtrip(GRAND_STAFF_XML)

    assert "<staves>" in xml


def test_grand_staff_split_preserves_original_part_name() -> None:
    """大谱表拆分后，声部名不应被 staff 后缀污染。"""
    original, restored, _ = _roundtrip(GRAND_STAFF_XML)

    assert [s.part_name for s in restored] == [s.part_name for s in original]
    assert all(s.part_name == "Piano" for s in restored)


def test_single_part_name_survives_jianpu_text_roundtrip() -> None:
    """单声部：声部名同样应被保留。"""
    original, restored, _ = _roundtrip(SINGLE_PART_XML)

    assert [s.part_name for s in restored] == [s.part_name for s in original]
