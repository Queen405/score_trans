"""小节编号金样例——锚定后端语义，供前端 gutter 对齐。

前端 `desktop/scripts/test-jianpu-page-sections.mjs` 使用**完全相同的样例文本**
断言 gutter 标签。任一侧语义变化时，对应测试应先变红；改动一侧必须同步另一侧。

编号真值 = `parse_jianpu_score` 的 flush 结果（`display_number` / `repeat_count`），
与渲染器 `_assign_score_measure_numbers` 的推进规则一致（每小节占 `repeat_count` 个号）。
"""

from __future__ import annotations

import pytest

from score_trans.domain.parse.jianpu_text import parse_jianpu_scores

HEADER = "1=C\n4/4\n"


def measure_rows(text: str) -> list[tuple[int, int]]:
    """返回 (小节号, 反复次数) 序列。"""
    rows: list[tuple[int, int]] = []
    for score in parse_jianpu_scores(text):
        for measure in score.measures:
            rows.append((measure.display_number, measure.repeat_count))
    return rows


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # 一行多小节：小节线才是边界，换行不是。
        (HEADER + "1 2 3 4 | 2 3 4 5 |", [(1, 1), (2, 1)]),
        (HEADER + "1 2 3 4 | 2 3 4 5 | 3 4 5 6 |", [(1, 1), (2, 1), (3, 1)]),
        (HEADER + "1 2 3 4 |\n2 3 4 5 |", [(1, 1), (2, 1)]),
        # 反复记号占用多个号。
        (HEADER + "1 2 3 4 *3 |", [(1, 3)]),
        (HEADER + "1 2 3 4 | *3", [(1, 3)]),
        # backward 反复是覆盖上一小节的 repeat_count，不是叠加。
        (HEADER + "1 2 *2 | *3", [(1, 3)]),
        # 反复结构：`|:`/`:|` 自身不产生空小节；`:|` 之后的空小节被吞掉。
        (HEADER + "|: 1 2 3 4 :|", [(1, 1)]),
        (HEADER + "|: 1 2 3 4 :| | 5 6 7 1 |", [(1, 1), (2, 1)]),
        # `1 2 3 4 :| *2 |` 中 `*2` 之后的 `|` 被 repeat_applied_backward 吞掉。
        (HEADER + "1 2 3 4 :| *2 |", [(1, 2)]),
        # 空小节（非 `:|`/`*N` 之后）保留为整小节休止，占号。
        (HEADER + "1 2 3 4 |\n|\n5 6 7 1 |", [(1, 1), (2, 1), (3, 1)]),
        # 末小节可以没有小节线（final flush）。
        (HEADER + "1 2 3 4 |\n5 6 7 1", [(1, 1), (2, 1)]),
        # 小节跨行：换行不产生新小节。
        (HEADER + "1 2 3 4 |\n5 6\n7 1 |", [(1, 1), (2, 1)]),
        # 行首 AI 小节号标签被剥离。
        (HEADER + "272: 1 2 3 4 |", [(1, 1)]),
        # 行内注释里的小节线不计数。
        (HEADER + "1 2 3 4 | // 注释 | 不应计数\n5 6 7 1 |", [(1, 1), (2, 1)]),
    ],
)
def test_measure_numbering(text: str, expected: list[tuple[int, int]]) -> None:
    assert measure_rows(text) == expected


def test_measure_numbering_across_pages_and_parts() -> None:
    text = (
        "// @page 1\n"
        '// @part 1 name="A"\n'
        "1 2 3 4 |\n"
        "1 2 3 4 | 5 6 7 1 |\n"
        '// @part 2 name="B"\n'
        "3 4 5 6 |\n"
        "1 1 1 1 |\n"
        "// @page 2\n"
        '// @part 1 name="A"\n'
        "2 2 2 2 |\n"
        '// @part 2 name="B"\n'
        "3 3 3 3 |"
    )
    scores = parse_jianpu_scores(text)
    # 各声部从本页起始号并行编号，因此两页的号都从 1 开始。
    assert [(score.part_name, score.page_index, len(score.measures)) for score in scores] == [
        ("A", 0, 3),
        ("B", 0, 2),
        ("A", 1, 1),
        ("B", 1, 1),
    ]
