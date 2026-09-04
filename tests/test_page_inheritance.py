from __future__ import annotations

from score_trans.domain.parse.jianpu_text import parse_jianpu_parts


def test_inherited_state_carries_meter_key_tempo_across_batch_pages() -> None:
    """批渲染路径：第 2 页省略拍号/调号/tempo 时，继承第 1 页末小节状态。"""
    page1 = "1=C\n4/4\n1 2 3 4 |\n3/8\n1=G\ntempo=80\n5 6 7 |"
    state: dict[int, tuple[str, int, int, int]] = {}
    parts1 = parse_jianpu_parts(page1, _inherited_state=state)
    last1 = parts1[-1].score.measures[-1]
    assert (
        last1.target_key,
        last1.beats_per_measure,
        last1.beat_type,
        last1.tempo,
    ) == (
        "G",
        3,
        8,
        80,
    )
    assert state[0] == ("G", 3, 8, 80)

    page2 = "5 6 7 |"
    parts2 = parse_jianpu_parts(page2, _inherited_state=state)
    m2 = parts2[0].score.measures[0]
    assert (m2.target_key, m2.beats_per_measure, m2.beat_type, m2.tempo) == (
        "G",
        3,
        8,
        80,
    )
    s2 = parts2[0].score
    assert s2.target_key == "G"
    assert s2.beats == 3
    assert s2.beat_type == 8


def test_explicit_meter_on_next_page_overrides_inherited() -> None:
    """第 2 页显式写 4/4 时，用 4/4 而非继承的 3/8。"""
    page1 = "1=C\n4/4\n1 2 3 4 |\n3/8\n5 6 7 |"
    state: dict[int, tuple[str, int, int, int]] = {}
    parse_jianpu_parts(page1, _inherited_state=state)
    assert state[0][1] == 3
    assert state[0][2] == 8

    page2 = "4/4\n1 2 3 4 |"
    parts2 = parse_jianpu_parts(page2, _inherited_state=state)
    m2 = parts2[0].score.measures[0]
    assert m2.beats_per_measure == 4
    assert m2.beat_type == 4


def test_whole_document_part_path_inherits_across_pages() -> None:
    """整篇 @part 路径：第 2 页省略拍号/调号时，内部 inherited_state 跨页继承。"""
    document = (
        "// @page 1\n"
        '// @part 1 name="v1"\n'
        "1=C\n4/4\n1 2 3 4 |\n3/8\n1=G\ntempo=80\n5 6 7 |\n"
        "// @page 2\n"
        '// @part 1 name="v1"\n'
        "5 6 7 |\n"
    )
    parts = parse_jianpu_parts(document)
    page2 = [p for p in parts if p.page_index == 1]
    assert page2
    m = page2[0].score.measures[0]
    assert (m.target_key, m.beats_per_measure, m.beat_type, m.tempo) == ("G", 3, 8, 80)


def test_fallback_to_last_part_when_part_count_changes() -> None:
    """声部数变化时回退到上一页最大 part_index 的状态。"""
    document = (
        "// @page 1\n"
        '// @part 1 name="v1"\n'
        "1=C\n4/4\n1 2 3 4 |\n3/8\n1=G\ntempo=80\n5 6 7 |\n"
        '// @part 2 name="v2"\n'
        "1 2 3 |\n"
        "// @page 2\n"
        '// @part 1 name="v1"\n'
        "5 6 7 |\n"
    )
    parts = parse_jianpu_parts(document)
    page2 = [p for p in parts if p.page_index == 1]
    assert page2
    m = page2[0].score.measures[0]
    assert (m.target_key, m.beats_per_measure, m.beat_type, m.tempo) == ("G", 3, 8, 80)
