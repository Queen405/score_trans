from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from score_trans.api.app import create_app
from score_trans.domain.parse.jianpu_text import (
    parse_jianpu_score,
    parse_jianpu_scores,
    validate_jianpu_text,
)


def test_validate_jianpu_text_returns_all_invalid_tokens() -> None:
    text = "1=C\n4/4\n1 45 2 89 |"

    diagnostics = validate_jianpu_text(text)

    assert [(item.line, item.column, item.start, item.end) for item in diagnostics] == [
        (3, 3, 10, 12),
        (3, 8, 15, 17),
    ]
    assert all(item.severity == "error" for item in diagnostics)
    assert "不支持的简谱 token：45" in diagnostics[0].message
    assert "不支持的简谱 token：89" in diagnostics[1].message


def test_validate_jianpu_text_uses_utf16_offsets_for_selection() -> None:
    text = "title=🎵乐谱\n1=C\n4/4\n45 |"

    diagnostics = validate_jianpu_text(text)

    assert len(diagnostics) == 1
    diagnostic = diagnostics[0]
    assert (diagnostic.line, diagnostic.column) == (4, 1)
    assert text.encode("utf-16-le")[: diagnostic.start * 2].decode("utf-16-le") == (
        "title=🎵乐谱\n1=C\n4/4\n"
    )
    assert diagnostic.end - diagnostic.start == 2


def test_validate_jianpu_text_stops_after_structural_error() -> None:
    diagnostics = validate_jianpu_text("1=C\n4/4\n$1$ 45 89 |")

    assert len(diagnostics) == 1
    assert "连音组至少需要两个音符" in diagnostics[0].message


def test_validate_wrapped_tuplet_reports_missing_closing_dollar() -> None:
    diagnostics = validate_jianpu_text("1=C\n4/4\n($12 |")

    assert len(diagnostics) == 1
    assert diagnostics[0].line == 3
    assert "连音组缺少结束标记 $" in diagnostics[0].message


def test_validate_jianpu_text_accepts_valid_score() -> None:
    assert validate_jianpu_text("1=C\n4/4\n1 2 3 4 |") == []


@pytest.mark.parametrize(
    "change",
    ["tempo=80\n5 6 7 1 |", "tempo=80 5 6 7 1 |"],
)
def test_validate_jianpu_text_accepts_measure_level_tempo(change: str) -> None:
    text = f"tempo=120\n1=C\n4/4\n1 2 3 4 |\n{change}"

    assert validate_jianpu_text(text) == []


def test_validate_jianpu_text_keeps_measure_duration_check_disabled_by_default() -> (
    None
):
    assert validate_jianpu_text("1=C\n4/4\n1 2 3 |") == []


def test_validate_jianpu_text_reports_measure_duration_warnings_when_enabled() -> None:
    text = "1=C\n4/4\n1 2 3 | 1 2 3 4 5 ||"

    diagnostics = validate_jianpu_text(text, check_measure_durations=True)

    assert [
        (item.severity, item.line, item.column, item.message) for item in diagnostics
    ] == [
        ("warning", 3, 1, "少拍：实际 3 拍，目标 4 拍"),
        ("warning", 3, 9, "超拍：实际 5 拍，目标 4 拍"),
    ]
    assert [item.measure for item in diagnostics] == ["1", "2"]
    assert [
        text.encode("utf-16-le")[item.start * 2 : item.end * 2].decode("utf-16-le")
        for item in diagnostics
    ] == [
        "1 2 3 |",
        "1 2 3 4 5 ||",
    ]


def test_validate_jianpu_text_keeps_duration_warnings_after_unrelated_syntax_error() -> (
    None
):
    text = "1=C\n4/4\n45 1 2 | 1 2 3 4 5 |"

    diagnostics = validate_jianpu_text(text, check_measure_durations=True)

    assert [(item.severity, item.message) for item in diagnostics] == [
        (
            "error",
            "不支持的简谱 token：45，请使用 1-7、0、#1、qs1、q1、[1+3+5] 等新语法",
        ),
        ("warning", "超拍：实际 5 拍，目标 4 拍"),
    ]
    warning = diagnostics[1]
    assert (
        text.encode("utf-16-le")[warning.start * 2 : warning.end * 2].decode(
            "utf-16-le"
        )
        == "1 2 3 4 5 |"
    )


def test_validate_jianpu_text_keeps_duration_warnings_after_contextual_error() -> None:
    text = "1=C\n4/4\n1 2 1=G 3 4 | 1 2 3 4 5 |"

    diagnostics = validate_jianpu_text(text, check_measure_durations=True)

    assert [(item.severity, item.message) for item in diagnostics] == [
        (
            "error",
            "调号 1=G 必须写在该小节音符之前，不能写在音符后面。"
            "请把调号移到小节开头或紧跟在小节线 | 之后。",
        ),
        ("warning", "超拍：实际 5 拍，目标 4 拍"),
    ]


def test_validate_jianpu_text_keeps_duration_warnings_after_header_error() -> None:
    text = "instrument=unknown\n1=C\n4/4\n1 2 3 4 5 |"

    diagnostics = validate_jianpu_text(text, check_measure_durations=True)

    assert [(item.severity, item.message) for item in diagnostics] == [
        (
            "error",
            "不支持的乐器模式 unknown，请使用 general、erhu、ruan、guzheng",
        ),
        ("warning", "超拍：实际 5 拍，目标 4 拍"),
    ]


def test_validate_jianpu_text_preserves_warning_offsets_after_utf16_error() -> None:
    text = "1=C\n4/4\n🎵 1 2 | 1 2 3 4 5 |"

    diagnostics = validate_jianpu_text(text, check_measure_durations=True)

    assert [item.severity for item in diagnostics] == ["error", "warning"]
    warning = diagnostics[1]
    assert (
        text.encode("utf-16-le")[warning.start * 2 : warning.end * 2].decode(
            "utf-16-le"
        )
        == "1 2 3 4 5 |"
    )


def test_validate_jianpu_text_warning_range_includes_measure_level_marks() -> None:
    text = "instrument=erhu\n1=C\n4/4\n(^l) 1 2 3 |"

    diagnostics = validate_jianpu_text(text, check_measure_durations=True)

    assert len(diagnostics) == 1
    diagnostic = diagnostics[0]
    assert (
        text.encode("utf-16-le")[diagnostic.start * 2 : diagnostic.end * 2].decode(
            "utf-16-le"
        )
        == "(^l) 1 2 3 |"
    )


def test_validate_jianpu_text_reports_contextual_error_after_token_checks() -> None:
    diagnostics = validate_jianpu_text("1=C\n4/4\n1 2 1=G 3 4 |")

    assert len(diagnostics) == 1
    assert diagnostics[0].line == 3
    assert diagnostics[0].column == 5
    assert "调号 1=G 必须写在该小节音符之前" in diagnostics[0].message


def test_validate_jianpu_text_returns_document_error_as_diagnostic() -> None:
    diagnostics = validate_jianpu_text("instrument=unknown\n1=C\n4/4\n1 2 3 4 |")

    assert len(diagnostics) == 1
    assert diagnostics[0].line == 1
    assert diagnostics[0].start == 0
    assert diagnostics[0].end == len("instrument=unknown")
    assert "不支持的乐器模式" in diagnostics[0].message


def test_validate_syntax_route_returns_structured_diagnostics() -> None:
    client = TestClient(create_app(auth_disabled=True))

    response = client.post("/syntax/validate", json={"jianpu_text": "1=C\n4/4\n45 |"})

    assert response.status_code == 200
    assert response.json() == {
        "diagnostics": [
            {
                "id": "syntax-error-3-1-8-10",
                "message": (
                    "不支持的简谱 token：45，请使用 1-7、0、#1、qs1、"
                    "q1、[1+3+5] 等新语法"
                ),
                "line": 3,
                "column": 1,
                "start": 8,
                "end": 10,
                "severity": "error",
                "measure": "1",
            }
        ]
    }


def test_validate_syntax_route_is_in_openapi() -> None:
    schema = create_app(auth_disabled=True).openapi()

    assert "/syntax/validate" in schema["paths"]
    response_schema = schema["components"]["schemas"]["SyntaxValidateResponse"]
    assert "diagnostics" in response_schema["properties"]


@pytest.mark.parametrize("time_signature", ["4/0", "0/4"])
def test_validate_jianpu_text_rejects_non_positive_time_signature(
    time_signature: str,
) -> None:
    diagnostics = validate_jianpu_text(f"1=C\n{time_signature}\n1 2 3 4 |")

    assert len(diagnostics) == 1
    diagnostic = diagnostics[0]
    assert (diagnostic.line, diagnostic.column) == (2, 1)
    assert (diagnostic.start, diagnostic.end) == (4, 7)
    assert f"拍号无效：{time_signature}" in diagnostic.message


@pytest.mark.parametrize("time_signature", ["4/0", "0/4"])
def test_strict_parse_rejects_non_positive_time_signature_as_value_error(
    time_signature: str,
) -> None:
    with pytest.raises(ValueError, match="拍号无效"):
        parse_jianpu_score(f"1=C\n{time_signature}\n1 2 3 4 |")
    with pytest.raises(ValueError, match="拍号无效"):
        parse_jianpu_scores(f"1=C\n{time_signature}\n1 2 3 4 |")


def test_validate_jianpu_text_rejects_mid_score_invalid_time_signature() -> None:
    diagnostics = validate_jianpu_text("1=C\n4/4\n1 2 4/0 |")

    assert len(diagnostics) == 1
    assert diagnostics[0].line == 3
    assert "拍号无效：4/0" in diagnostics[0].message


def test_validate_jianpu_text_reports_tempo_error_line_and_message() -> None:
    text = "title=x\n1=C\n4/4\n1 2 |\ntempo=abc"

    diagnostics = validate_jianpu_text(text)

    assert len(diagnostics) == 1
    diagnostic = diagnostics[0]
    assert diagnostic.line == 5
    assert diagnostic.message == "tempo 必须是 20 到 300 之间的整数：abc"
    selected = text.encode("utf-16-le")[diagnostic.start * 2 : diagnostic.end * 2]
    assert selected.decode("utf-16-le") == "tempo=abc"


def test_validate_jianpu_text_reports_mark_target_error_at_token_line() -> None:
    diagnostics = validate_jianpu_text("instrument=ruan\n1=C\n4/4\n^py 1 2 3 4 |")

    assert len(diagnostics) == 1
    assert diagnostics[0].line == 4
    assert "必须跟随和弦" in diagnostics[0].message


def test_validate_jianpu_text_reports_body_before_first_part_marker() -> None:
    diagnostics = validate_jianpu_text(
        '1 2 |\n// @part 1 name="a"\n1=C\n4/4\n1 2 3 4 |'
    )

    assert len(diagnostics) == 1
    assert diagnostics[0].line == 2
    assert "第一个分谱标记之前不能包含简谱正文" in diagnostics[0].message


def test_validate_jianpu_text_reports_invalid_part_name_json() -> None:
    diagnostics = validate_jianpu_text('// @part 1 name="a\\x"\n1=C\n4/4\n1 2 3 4 |')

    assert len(diagnostics) == 1
    assert diagnostics[0].line == 1
    assert "分谱名称不是有效 JSON 字符串" in diagnostics[0].message


def test_validate_jianpu_text_reports_part_measure_count_mismatch() -> None:
    text = (
        '// @part 1 name="a"\n1=C\n4/4\n1 2 3 4 | 5 6 7 1 |\n'
        '// @part 2 name="b"\n1=C\n4/4\n1 2 3 4 |'
    )

    diagnostics = validate_jianpu_text(text)

    assert len(diagnostics) == 1
    assert diagnostics[0].line == 1
    assert "各声部小节数量不一致：a=2、b=1" in diagnostics[0].message
    # v1：这条诊断降级为 warning（不阻塞流程，前端「隐藏警告」可关闭）。
    assert diagnostics[0].severity == "warning"


def test_validate_jianpu_text_reports_measure_duration_warnings_in_document_offsets() -> (
    None
):
    text = (
        '// @part 1 name="a"\n1=C\n4/4\n1 2 3 |\n'
        '// @part 2 name="b"\n1=C\n4/4\n1 2 3 4 5 |'
    )

    diagnostics = validate_jianpu_text(text, check_measure_durations=True)

    assert [(item.line, item.column, item.severity) for item in diagnostics] == [
        (4, 1, "warning"),
        (8, 1, "warning"),
    ]
    assert [
        text.encode("utf-16-le")[item.start * 2 : item.end * 2].decode("utf-16-le")
        for item in diagnostics
    ] == ["1 2 3 |", "1 2 3 4 5 |"]


def test_validate_jianpu_text_excludes_standalone_page_header_from_warning_range() -> (
    None
):
    text = "// @page 1\n1=C\n4/4\n1 2 3 4 |\n1 2 3 4 |\n// @page 2\n1=C\n4/4\n1 2 3 |\n"

    diagnostics = validate_jianpu_text(text, check_measure_durations=True)

    assert len(diagnostics) == 1
    diagnostic = diagnostics[0]
    assert diagnostic.measure == "3"
    selected = text.encode("utf-16-le")[
        diagnostic.start * 2 : diagnostic.end * 2
    ].decode("utf-16-le")
    assert selected == "1 2 3 |"
    assert diagnostic.line == 9


def test_validate_jianpu_text_keeps_inline_key_time_in_warning_range() -> None:
    text = "1=C\n4/4\n1 2 3 4 |\n1=G 3/4 1 2 |\n"

    diagnostics = validate_jianpu_text(text, check_measure_durations=True)

    assert len(diagnostics) == 1
    diagnostic = diagnostics[0]
    selected = text.encode("utf-16-le")[
        diagnostic.start * 2 : diagnostic.end * 2
    ].decode("utf-16-le")
    assert selected == "1=G 3/4 1 2 |"


def test_validate_jianpu_text_accepts_valid_multi_part_score() -> None:
    text = (
        '// @part 1 name="a"\n1=C\n4/4\n1 2 3 4 |\n'
        '// @part 2 name="b"\n1=C\n4/4\n5 6 7 1 |'
    )

    assert validate_jianpu_text(text) == []


def test_validate_jianpu_text_reports_part_body_error_at_document_position() -> None:
    text = (
        '// @part 1 name="a"\n1=C\n4/4\n1 2 3 4 |\n'
        '// @part 2 name="b"\n1=C\n4/4\n1 2 45 3 |'
    )

    diagnostics = validate_jianpu_text(text)

    assert len(diagnostics) == 1
    diagnostic = diagnostics[0]
    assert diagnostic.line == 8
    selected = text.encode("utf-16-le")[diagnostic.start * 2 : diagnostic.end * 2]
    assert selected.decode("utf-16-le") == "45"


def test_validate_jianpu_text_reports_tuplet_member_offsets() -> None:
    text = "1=C\n4/4\n1 2 3 4 |\n$19$"

    diagnostics = validate_jianpu_text(text)

    assert len(diagnostics) == 1
    diagnostic = diagnostics[0]
    assert (diagnostic.line, diagnostic.column) == (4, 2)
    assert diagnostic.end > diagnostic.start > 0
    selected = text.encode("utf-16-le")[diagnostic.start * 2 : diagnostic.end * 2]
    assert selected.decode("utf-16-le") == "19"


def test_validate_jianpu_text_reports_compact_tuplet_member_after_marks() -> None:
    text = "1=C\n4/4\n$^>19$ |"

    diagnostics = validate_jianpu_text(text)

    assert len(diagnostics) == 1
    diagnostic = diagnostics[0]
    assert diagnostic.end > diagnostic.start > 0
    selected = text.encode("utf-16-le")[diagnostic.start * 2 : diagnostic.end * 2]
    assert selected.decode("utf-16-le") == "19"


# ---------------------------------------------------------------------------
# v1 回归：多页文档的小节数校验 / 页眉配置归属 / 按页连续小节号
# 对应 docs/syntax-measure-numbering-fix-plan.md 的用例 A / B / C / G。
# ---------------------------------------------------------------------------


def test_page_grouped_measure_counts_accept_multi_page_single_part() -> None:
    # 用例 A：单声部两页。每页的小节数天然不同，不应再误报「小节数量不一致」。
    text = (
        '// @page 1 name="p1.png"\n'
        '// @part 1 name="旋律"\n'
        "1=C\n4/4\n"
        "1 2 3 4 | 5 6 7 1' |\n"
        "2 3 4 5 |\n"
        '// @page 2 name="p2.png"\n'
        '// @part 1 name="旋律"\n'
        "1=C\n4/4\n"
        "3 4 5 6 | 7 1' 2' 3' |\n"
    )

    assert validate_jianpu_text(text, check_measure_durations=True) == []


def test_page_header_config_belongs_to_next_page_part() -> None:
    # 用例 B：第 2 页的调号/拍号写在 @part 之前，且第 1 页末小节已收尾。
    # 2/4 必须作用于第 2 页（3 4 | 恰好 2 拍），而不是被吞进第 1 页声部。
    text = (
        '// @page 1 name="p1.png"\n'
        '// @part 1 name="A"\n'
        "1=C\n4/4\n"
        "1 2 3 4 |\n"
        '// @page 2 name="p2.png"\n'
        "1=C\n2/4\n"
        '// @part 1 name="A"\n'
        "3 4 | 5 6 |\n"
    )

    assert validate_jianpu_text(text, check_measure_durations=True) == []
    scores = parse_jianpu_scores(text)
    assert (scores[1].beats, scores[1].beat_type) == (2, 4)


def test_page_header_config_after_unterminated_measure() -> None:
    # 用例 C：第 2 页配置写在 @part 之前，且第 1 页末小节没有小节线。
    # 不应误报「调号必须写在该小节音符之前」。
    text = (
        '// @page 1 name="p1.png"\n'
        '// @part 1 name="旋律"\n'
        "1=C\n4/4\n"
        "1 2 3 4 | 5 6 7 1'\n"
        '// @page 2 name="p2.png"\n'
        "1=C\n4/4\n"
        '// @part 1 name="旋律"\n'
        "2 3 4 5 |\n"
    )

    assert validate_jianpu_text(text, check_measure_durations=True) == []


def test_cross_page_measure_numbers_are_continuous() -> None:
    # 用例 G：第 1 页每声部 1 小节 → 第 2 页起始号 = 2；
    # 左手第 2 页的第 2/3 小节 → 连续号 3/4。
    text = (
        '// @page 1 name="p1.png"\n'
        '// @part 1 name="右手"\n'
        "1=C\n4/4\n"
        "1 2 3 4 |\n"
        '// @part 2 name="左手"\n'
        "1=C\n4/4\n"
        "w1 w1 |\n"
        '// @page 2 name="p2.png"\n'
        '// @part 1 name="右手"\n'
        "1=C\n4/4\n"
        "2 3 4 5 |\n"
        '// @part 2 name="左手"\n'
        "1=C\n4/4\n"
        "w3 w4 |\n"
        "5 6 7 8 | 1 2 99 |\n"
    )

    diagnostics = validate_jianpu_text(text, check_measure_durations=True)
    errors = [d for d in diagnostics if d.severity == "error"]

    assert [(d.line, d.measure) for d in errors] == [(19, "3"), (19, "4")]
    warnings = [d for d in diagnostics if d.severity == "warning"]
    # 警告侧与错误侧同一套号：第 2 页左手的超拍小节是连续号 2。
    duration_warnings = [d for d in warnings if "超拍" in d.message]
    assert [d.measure for d in duration_warnings] == ["1", "2"]


def test_page_without_part_marker_is_reported() -> None:
    # F6：用了 @part 的文档里，某页缺 @part 不应静默并入上一页声部，应报错。
    text = (
        '// @page 1 name="p1.png"\n'
        '// @part 1 name="A"\n'
        "1=C\n4/4\n"
        "1 2 3 4 |\n"
        '// @page 2 name="p2.png"\n'
        "1=C\n4/4\n"
        "2 3 4 5 |\n"
    )

    diagnostics = validate_jianpu_text(text, check_measure_durations=True)

    assert any("缺少分谱标记" in d.message and d.line == 6 for d in diagnostics)


def test_page_without_part_marker_is_ok_when_no_part_at_all() -> None:
    # F6 兼容：完全无 @part 的多页文档（单声部）走整篇一个 score，不受影响。
    text = (
        '// @page 1 name="p1.png"\n'
        "1=C\n4/4\n"
        "1 2 3 4 |\n"
        '// @page 2 name="p2.png"\n'
        "2 3 4 5 |\n"
    )

    assert validate_jianpu_text(text, check_measure_durations=True) == []


def test_measure_numbers_respect_forward_repeat_in_error_report() -> None:
    # T8：段内 forward 反复 `*3` 应让下一个小节占正确的连续号。
    # 1 2 3 4 *3 占号 1-3，5 6 7 8 是 display 4；8 应报第 4 小节。
    text = (
        '// @page 1 name="p1.png"\n'
        '// @part 1 name="A"\n'
        "1=C\n4/4\n"
        "1 2 3 4 *3 | 5 6 7 8 |\n"
    )

    diagnostics = validate_jianpu_text(text, check_measure_durations=True)
    errors = [d for d in diagnostics if d.severity == "error"]

    assert [(d.line, d.measure) for d in errors] == [(5, "4")]


def test_measure_numbers_respect_backward_repeat_in_error_report() -> None:
    # T8：段内 backward `*2` 覆盖上一小节反复次数；8 应报第 3 小节。
    text = (
        '// @page 1 name="p1.png"\n'
        '// @part 1 name="A"\n'
        "1=C\n4/4\n"
        "1 2 3 4 | *2 5 6 7 8 |\n"
    )

    diagnostics = validate_jianpu_text(text, check_measure_durations=True)
    errors = [d for d in diagnostics if d.severity == "error"]

    assert [(d.line, d.measure) for d in errors] == [(5, "3")]


def test_measure_numbers_swallow_empty_bar_after_repeat_end() -> None:
    # T8：`:|` 之后的空 `|` 被吞掉不占号；8 应报第 2 小节。
    text = "1=C\n4/4\n|: 1 2 3 4 :| | 5 6 7 8 |"

    diagnostics = validate_jianpu_text(text, check_measure_durations=True)
    errors = [d for d in diagnostics if d.severity == "error"]

    assert [(d.line, d.measure) for d in errors] == [(3, "2")]
