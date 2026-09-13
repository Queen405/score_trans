"""多声部渲染入口测试。

守护 F1：从 MusicXML 渲染时，不得只画第一个声部。

历史上 `RenderMusicXmlJianpuAction.execute()` 与 `execute_page()` 走的是
`build_score()`（内部返回 `scores[0]`），多声部谱面因此被静默截断为第一声部；
只有 `execute_a4_pages()` 走 `build_scores()` 是正确的。
"""

from __future__ import annotations

from pathlib import Path

from score_trans.exec.render.actions import RenderMusicXmlJianpuAction

# 两个独立 part，声部名不同，便于在 SVG 中区分
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


def _write(tmp_path: Path) -> Path:
    path = tmp_path / "score.musicxml"
    path.write_text(TWO_PARTS_XML, encoding="utf-8")
    return path


def test_execute_page_renders_every_part(tmp_path: Path) -> None:
    """定尺寸渲染：两个声部都应出现在 SVG 中。"""
    output = tmp_path / "out.svg"
    RenderMusicXmlJianpuAction().execute_page(
        _write(tmp_path),
        output,
        page_width=1240.0,
        page_height=1754.0,
    )

    svg = output.read_text(encoding="utf-8")
    assert "高声部" in svg
    assert "低声部" in svg
    # 两个声部各 1 小节，共 2 个 measure；修复前只渲染第一声部，此处为 1
    assert svg.count('class="measure"') == 2


def test_execute_renders_every_part(tmp_path: Path) -> None:
    """自适应高度渲染：两个声部都应出现在 SVG 中。"""
    output = tmp_path / "out.svg"
    RenderMusicXmlJianpuAction().execute(_write(tmp_path), output)

    svg = output.read_text(encoding="utf-8")
    assert "高声部" in svg
    assert "低声部" in svg
    assert svg.count('class="measure"') == 2


def test_execute_a4_pages_renders_every_part(tmp_path: Path) -> None:
    """A4 分页渲染：这条路径本来就是对的，作为对照组防止回退。"""
    pages = RenderMusicXmlJianpuAction().execute_a4_pages(
        _write(tmp_path),
        tmp_path / "page",
    )

    assert pages
    svg = pages[0].path.read_text(encoding="utf-8")
    assert "高声部" in svg
    assert "低声部" in svg


def test_first_score_still_returns_only_the_leading_part(tmp_path: Path) -> None:
    """first_score() 的语义就是只取首个声部，渲染与导出不应使用它。"""
    score = RenderMusicXmlJianpuAction().first_score(_write(tmp_path))

    assert score.part_name == "高声部"


# ── 多声部播放分组（data-note-group）与节拍对齐 ──


import re  # noqa: E402
from typing import NamedTuple  # noqa: E402

import mido  # noqa: E402

from score_trans.domain.jianpu import parse_jianpu_score  # noqa: E402
from score_trans.models.score import JianpuScore  # noqa: E402
from score_trans.services.export.export_service import ExportService  # noqa: E402
from score_trans.services.render.engraving.renderer import (  # noqa: E402
    PublicationRenderer,
)


def _part(text: str, index: int, count: int, name: str = "") -> JianpuScore:
    score = parse_jianpu_score(text)
    score.part_count = count
    score.part_index = index
    score.part_name = name
    return score


class _PlaybackNote(NamedTuple):
    group: int
    note_index: int
    y: float
    x: float


def _playback_notes(svg: str) -> list[_PlaybackNote]:
    """提取 SVG 中每个播放音符的 (group, index, y, event_x)。"""
    notes: list[_PlaybackNote] = []
    for match in re.finditer(
        r'<g class="playback-note[^"]*"([^>]*)>(.*?)</g>\s*</g>', svg, re.S
    ):
        attrs, body = match.groups()
        group = re.search(r'data-note-group="(\d+)"', attrs)
        index = re.search(r'data-note-index="(\d+)"', attrs)
        bbox = re.search(r'data-bbox="([^"]+)"', attrs)
        transform = re.search(r'transform="translate\(([\d.]+) ', body)
        assert group and index and bbox and transform
        notes.append(
            _PlaybackNote(
                group=int(group.group(1)),
                note_index=int(index.group(1)),
                y=float(bbox.group(1).split()[1]),
                x=float(transform.group(1)),
            )
        )
    return notes


def test_shared_onsets_share_group_and_exact_position() -> None:
    """四分音符声部与八分音符声部：同拍点的音符 group 相同且 x 完全相等。"""
    high = _part("1=C 2/4\n1 2 | 3 5 |", 0, 2, "高")
    low = _part("1=C 2/4\nq1 q2 q3 q4 | q6 q7 q1 q2 |", 1, 2, "低")
    pages = PublicationRenderer().render_scores([high, low], title="t")

    assert pages[0].note_group_start == 0
    assert pages[0].note_group_end == 7
    notes = _playback_notes(pages[0].svg)
    by_group: dict[int, list[_PlaybackNote]] = {}
    for note in notes:
        by_group.setdefault(note.group, []).append(note)
    assert sorted(by_group) == list(range(8))
    # 拍点 0/1/2/3 由两个声部共享；分组 0/2/4/6 必须各含两个声部且 x 一致
    for shared in (0, 2, 4, 6):
        members = by_group[shared]
        assert len(members) == 2
        assert len({round(note.x, 6) for note in members}) == 1
        assert len({round(note.y, 1) for note in members}) == 2
    # 分组即时间序：低声部（八分音符）的组号必须沿 x 严格递增
    high_row = min(note.y for note in notes)
    low_notes = sorted(
        (note for note in notes if note.y != high_row),
        key=lambda note: note.x,
    )
    assert [note.group for note in low_notes] == sorted(
        note.group for note in low_notes
    )


def test_multi_part_multipage_title_only_on_first_page() -> None:
    """多声部跨页时，曲名只应出现在首页。"""
    parts = [
        _part("1=C 4/4\n" + "1 2 3 4 | " * 18, 0, 2, "高"),
        _part("1=C 4/4\n" + "5 6 7 1 | " * 18, 1, 2, "低"),
    ]
    pages = PublicationRenderer().render_scores(
        parts, title="标题", page_width=900.0, page_height=700.0
    )

    assert len(pages) > 1
    assert sum(page.svg.count('class="score-title"') for page in pages) == 1
    assert pages[0].svg.count('class="score-title"') == 1
    assert all('class="score-title"' not in page.svg for page in pages[1:])


def test_three_parts_share_first_onset() -> None:
    """三声部：小节起点的同拍音符共用一个 group 且 x 对齐。"""
    parts = [
        _part("1=C 4/4\n1 2 3 4 |", 0, 3, "一"),
        _part("1=C 4/4\n1 0 0 0 |", 1, 3, "二"),
        _part("1=C 4/4\nq1 q1 q1 q1 q1 q1 q1 q1 |", 2, 3, "三"),
    ]
    svg = PublicationRenderer().render_scores(parts, title="t")[0].svg
    notes = _playback_notes(svg)
    first = [note for note in notes if note.group == 0]
    assert len(first) == 3
    assert len({round(note.x, 6) for note in first}) == 1


def test_rest_and_chord_group_semantics() -> None:
    """休止符不占播放组；和弦（一个事件多个音）只占一个播放组。"""
    score = parse_jianpu_score("1=C 4/4\n1 0 [1+3+5] 2 |")
    svg = PublicationRenderer().render_scores([score], title="t")[0].svg
    notes = _playback_notes(svg)
    # 1、和弦、2 三个发声事件；休止符 0 不出现
    assert len(notes) == 3
    assert [note.group for note in notes] == [0, 1, 2]


def test_midi_group_sequence_matches_render_groups(tmp_path: Path) -> None:
    """核心不变量：MIDI 同起点合并后的组序列与渲染分组一一对应。"""
    high = _part("1=C 2/4\n1 2 | [1+3] 5 |", 0, 2, "高")
    low = _part("1=C 2/4\nq1 q2 q3 q4 | q6 q7 q1 q2 |", 1, 2, "低")
    midi_path = tmp_path / "out.mid"
    ExportService().export_midi_scores([high, low], midi_path)

    onsets: set[int] = set()
    mid = mido.MidiFile(midi_path)
    for track in mid.tracks:
        tick = 0
        for message in track:
            tick += message.time
            if message.type == "note_on" and message.velocity > 0:
                onsets.add(tick)
    midi_group_count = len(onsets)

    pages = PublicationRenderer().render_scores([high, low], title="t")
    render_groups = {note.group for page in pages for note in _playback_notes(page.svg)}
    assert render_groups == set(range(midi_group_count))


def test_multi_page_parts_merge_by_within_page_rank() -> None:
    """跨 @page 时全局 part_index 仍应合并为连续的两个声部。"""
    from score_trans.domain.parse.jianpu_text import parse_jianpu_parts
    from score_trans.services.render.engraving.renderer import _normalize_parts

    text = (
        '// @page 1 name="p1"\n'
        '// @part 1 name="高"\n1=C\n3/8\n1 |\n'
        '// @part 2 name="低"\n1=C\n3/8\n5 |\n'
        '// @page 2 name="p2"\n'
        '// @part 1 name="高"\n1=C\n3/8\n2 |\n'
        '// @part 2 name="低"\n1=C\n3/8\n6 |\n'
    )
    scores = [part.score for part in parse_jianpu_parts(text)]
    parts = _normalize_parts(scores)

    assert len(parts) == 2
    assert [len(part) for part in parts] == [2, 2]
    assert [score.part_index for score in parts[0]] == [0, 2]
    assert [score.part_index for score in parts[1]] == [1, 3]
