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
