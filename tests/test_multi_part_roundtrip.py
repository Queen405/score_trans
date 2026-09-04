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


def test_polyphonic_score_is_rejected_before_text_conversion() -> None:
    """复调：多 voice 声部在转简谱文本前即被拦截（F2-A 止损）。"""
    from score_trans.models.common.errors import MultiVoiceNotSupportedError

    scores = musicxml_to_scores(TWO_VOICES_XML)
    with pytest.raises(MultiVoiceNotSupportedError):
        scores_to_jianpu_document(scores)


# --------------------------------------------------------------------------
# F2-A 复调止损：同声部多 voice 转简谱文本时明确报错，不再静默拍平
# --------------------------------------------------------------------------


def test_polyphonic_score_raises_multi_voice_error() -> None:
    """复调：含多 voice 的声部转简谱文本应抛 MultiVoiceNotSupportedError。"""
    from score_trans.models.common.errors import MultiVoiceNotSupportedError

    scores = musicxml_to_scores(TWO_VOICES_XML)
    with pytest.raises(MultiVoiceNotSupportedError, match="2 个 voice"):
        scores_to_jianpu_document(scores)


def test_multi_voice_error_message_contains_part_name() -> None:
    """报错信息应包含声部名，便于用户定位。"""
    from score_trans.models.common.errors import MultiVoiceNotSupportedError

    scores = musicxml_to_scores(TWO_VOICES_XML)
    with pytest.raises(MultiVoiceNotSupportedError, match="Flute"):
        scores_to_jianpu_document(scores)


def test_single_voice_score_does_not_raise() -> None:
    """单 voice 声部不受止损拦截。"""
    scores = musicxml_to_scores(TWO_PARTS_XML)
    # 不应抛错
    scores_to_jianpu_document(scores)


def test_multi_voice_error_has_stable_code() -> None:
    """异常应携带稳定的 error_code 供 API 层路由。"""
    from score_trans.models.common.errors import MultiVoiceNotSupportedError

    scores = musicxml_to_scores(TWO_VOICES_XML)
    try:
        scores_to_jianpu_document(scores)
    except MultiVoiceNotSupportedError as exc:
        assert exc.error_code == "multi_voice_not_supported"
    else:
        pytest.fail("应抛出 MultiVoiceNotSupportedError")


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
