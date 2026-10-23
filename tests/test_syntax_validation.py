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


def test_validate_jianpu_text_accepts_ending_houses() -> None:
    assert (
        validate_jianpu_text("1=C\n4/4\n|: 1 2 3 4 | {1.} 5 6 5 4 :| {2.} 7 1' h2' ||")
        == []
    )


def test_validate_ending_marker_mid_measure_reports_position() -> None:
    diagnostics = validate_jianpu_text("1=C\n4/4\n1 2 {1.} 3 4 |")

    assert len(diagnostics) == 1
    assert diagnostics[0].severity == "error"
    assert (diagnostics[0].line, diagnostics[0].column) == (3, 5)
    assert "必须写在小节第一个音符之前" in diagnostics[0].message


def test_validate_ending_duplicate_number_reports_position() -> None:
    diagnostics = validate_jianpu_text("{1.} 1 2 3 4 | {1.} 2 3 4 5 |")

    assert len(diagnostics) == 1
    assert (diagnostics[0].line, diagnostics[0].column) == (1, 16)
    assert "同一反复组内重复" in diagnostics[0].message


def test_validate_ending_close_without_open_house() -> None:
    diagnostics = validate_jianpu_text("{.} 1 2 3 4 |")

    assert len(diagnostics) == 1
    assert "没有开着的房子" in diagnostics[0].message


def test_validate_ending_malformed_brace() -> None:
    diagnostics = validate_jianpu_text("{x.} 1 2 3 4 |")

    assert len(diagnostics) == 1
    assert "房子标记格式无效" in diagnostics[0].message


def test_validate_warns_on_repeat_inside_ending_house() -> None:
    diagnostics = validate_jianpu_text(
        "1=C\n4/4\n|: 1 2 3 4 | {1.} 5 6 5 4 | |: 1 2 3 4 :| {2.} 7 1' 2' 1' |"
    )

    warnings = [item for item in diagnostics if item.severity == "warning"]
    assert warnings
    assert "跳房子" in warnings[0].message
    assert warnings[0].measure == "3"


def test_timed_lyric_overflow_is_a_warning_and_summary_counts_words() -> None:
    client = TestClient(create_app(auth_disabled=True))

    response = client.post(
        "/syntax/validate",
        json={"jianpu_text": "1=C\n4/4\n1 2 3 4 |\n/L: w春 q眠/"},
    )

    assert response.status_code == 200
    assert response.json()["lyrics"] == [
        {
            "verse": 1,
            "words": 2,
        }
    ]
    assert any(
        item["severity"] == "warning" and "歌词时值超出小节范围" in item["message"]
        for item in response.json()["diagnostics"]
    )


def test_slash_lyric_block_is_reported_by_validation() -> None:
    client = TestClient(create_app(auth_disabled=True))

    response = client.post(
        "/syntax/validate",
        json={"jianpu_text": "1=C\n4/4\n1 2 3 4 |\n/L: 春 风 雨 云 雪/"},
    )

    assert response.json()["lyrics"][0]["words"] == 5
    assert response.json()["diagnostics"]


@pytest.mark.parametrize(
    "lyric_text, message",
    [
        ("1 2 3 4 | /L: 一 二/", "单独写在一行"),
        ("/L: 一/\n/L: 二/", "只允许一个"),
        # W2：结束符改为 `/L:` 后第一个独立 `/`，其后内容报"结束后不能有内容"。
        ("/L: 一 / 二/", "结束符 / 后不能有内容"),
        ("/L: 一/二/", "结束符 / 后不能有内容"),
        # 块内的 `//` 不是结束符，命中保留符号检查。
        ("/L: 一 // 注释\n二/", "不能包含保留符号"),
        ("L: 一 二", "旧歌词语法已移除"),
        ("L2: 一 二", "旧歌词语法已移除"),
    ],
)
def test_lyric_block_shape_and_removed_legacy_syntax(lyric_text, message) -> None:
    assert any(
        message in item.message
        for item in validate_jianpu_text(f"1=C\n4/4\n1 2 3 4 |\n{lyric_text}")
    )


def test_lyric_block_spans_multiple_lines() -> None:
    # W2：歌词块可跨行，换行等同空白，小节仍由 | 划分。
    score = parse_jianpu_score(
        "1=C\n4/4\n1 2 3 4 | 5 6 7 1 |\n/L: 一 二 三 四 |\n五 六 七 一/"
    )

    assert [
        [event.lyric for event in measure.events if event.kind == "note"]
        for measure in score.measures
    ] == [["一", "二", "三", "四"], ["五", "六", "七", "一"]]


def test_lyric_block_newline_is_plain_whitespace() -> None:
    # W2：小节中段的换行不改变词项归属；& 歌词流同样可跨行。
    score = parse_jianpu_score(
        "1=C\n4/4\n1 2 | 3 4 |\n/L: 一\n二 & A\nB | 三\n四 & C\nD/"
    )

    assert [
        [event.lyric for event in measure.events if event.kind == "note"]
        for measure in score.measures
    ] == [["一", "二"], ["三", "四"]]
    assert [
        [event.lyrics.get(2) for event in measure.events if event.kind == "note"]
        for measure in score.measures
    ] == [["A", "B"], ["C", "D"]]


def test_lyric_block_multiline_unterminated_and_trailing_content() -> None:
    unterminated = validate_jianpu_text("1=C\n4/4\n1 2 3 4 |\n/L: 一 二\n三 四")
    assert any("歌词块缺少结束符" in item.message for item in unterminated)

    # 未闭合块后接注释行仍报缺少结束符（`//` 不会被误认为结束符）。
    with_comment = validate_jianpu_text("1=C\n4/4\n1 2 3 4 |\n/L: 一 二\n// 注释")
    assert any("歌词块缺少结束符" in item.message for item in with_comment)

    trailing = validate_jianpu_text("1=C\n4/4\n1 2 3 4 |\n/L: 一 二 |\n三 四/ 多余")
    assert any("结束符 / 后不能有内容" in item.message for item in trailing)


def test_lyric_block_multiline_errors_anchor_to_actual_line() -> None:
    # W2：多行块的内容错误锚定到出错小节/词的实际行列，而非 /L: 行。
    lane_mismatch = validate_jianpu_text(
        "1=C\n4/4\n1 2 | 3 4 |\n/L: 一 二 & A B |\n三 四/"
    )
    lane_errors = [item for item in lane_mismatch if "& 分隔流" in item.message]
    assert [(item.line, item.column) for item in lane_errors] == [(5, 1)]

    missing_word = validate_jianpu_text("1=C\n4/4\n1 2 | 3 4 |\n/L: 一 二 |\n三 q/")
    word_errors = [
        item for item in missing_word if "时值前缀后缺少歌词" in item.message
    ]
    assert [(item.line, item.column) for item in word_errors] == [(5, 3)]


def test_lyric_block_multiline_in_multi_part_document() -> None:
    # W2：多声部文档中每个声部段可各自携带多行歌词块（按段解析路径）。
    score_a, score_b = parse_jianpu_scores(
        '// @page 1 name="p1"\n'
        '// @part 1 name="a"\n'
        "1 2 | 3 4 |\n"
        "/L: 一 二 |\n三 四/\n"
        '// @part 2 name="b"\n'
        "5 6 | 7 1 |\n"
        "/L: 五 六 |\n七 一/"
    )

    assert [
        [event.lyric for event in measure.events if event.kind == "note"]
        for measure in score_a.measures
    ] == [["一", "二"], ["三", "四"]]
    assert [
        [event.lyric for event in measure.events if event.kind == "note"]
        for measure in score_b.measures
    ] == [["五", "六"], ["七", "一"]]


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
        "lyrics": [],
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
        ],
    }


def test_validate_syntax_route_is_in_openapi() -> None:
    schema = create_app(auth_disabled=True).openapi()

    assert "/syntax/validate" in schema["paths"]
    response_schema = schema["components"]["schemas"]["SyntaxValidateResponse"]
    assert "diagnostics" in response_schema["properties"]
    assert "lyrics" in response_schema["properties"]


def test_validate_syntax_reports_lyric_overflow_and_summary() -> None:
    client = TestClient(create_app(auth_disabled=True))
    response = client.post(
        "/syntax/validate",
        json={"jianpu_text": "1=C\n4/4\n1 2 3 4 |\n/L: w春 q眠/"},
    )

    assert response.status_code == 200
    assert response.json()["lyrics"] == [
        {
            "verse": 1,
            "words": 2,
        }
    ]
    assert any(
        item["severity"] == "warning" and "歌词时值超出小节范围" in item["message"]
        for item in response.json()["diagnostics"]
    )


def test_validate_syntax_rejects_legacy_lyric_syntax() -> None:
    client = TestClient(create_app(auth_disabled=True))
    response = client.post(
        "/syntax/validate",
        json={"jianpu_text": "1=C\n4/4\n1 2 3 4 |\n/L: 春 风 雨 云 雪/"},
    )

    assert response.json()["lyrics"][0]["words"] == 5
    assert response.json()["diagnostics"]


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


def test_validate_jianpu_text_accepts_voice_lane_separator() -> None:
    text = "1=C\n4/4\n0 [1+3] [1+3] [1+3] & w1, |\n"

    assert validate_jianpu_text(text, check_measure_durations=True) == []


def test_validate_jianpu_text_reports_lane_errors_with_positions() -> None:
    # lane 1 为空：定位到小节开头（小节级错误不再指向小节线）
    diagnostics = validate_jianpu_text("1=C\n4/4\n& 5 5 |\n")
    assert len(diagnostics) == 1
    assert "声线分隔符" in diagnostics[0].message
    assert (diagnostics[0].line, diagnostics[0].column) == (3, 1)

    # lane 1 超拍：定位到该小节开头，诊断范围覆盖整个出错小节
    diagnostics = validate_jianpu_text("1=C\n4/4\n5 5 5 5 5 & w1 |\n")
    assert len(diagnostics) == 1
    assert "第 1 声线超拍" in diagnostics[0].message
    assert (diagnostics[0].line, diagnostics[0].column) == (3, 1)

    # 声线为空：定位到引入该声线的 &
    diagnostics = validate_jianpu_text("1=C\n4/4\n5 5 5 5 | 1 2 & |\n")
    assert len(diagnostics) == 1
    assert "第 2 声线不能为空" in diagnostics[0].message
    assert (diagnostics[0].line, diagnostics[0].column) == (3, 15)

    # 连音组内不允许 &
    diagnostics = validate_jianpu_text("1=C\n4/4\n$1 & 2$ 5 5 5 |\n")
    assert len(diagnostics) == 1
    assert "连音组内不允许声线分隔符" in diagnostics[0].message


def test_validate_jianpu_text_lane_overflow_does_not_cascade() -> None:
    """超拍诊断的范围必须覆盖整个出错小节，mask 重试不会级联出错位重复诊断。"""
    text = "1=C\n4/4\n1 2 3 4 |\n2 2 2 2 2 & 0 2 2 2 |\n3 3 3 3 & 0 3 3 3 |\n"

    diagnostics = validate_jianpu_text(text, check_measure_durations=True)

    assert len(diagnostics) == 1
    assert "第 1 声线超拍" in diagnostics[0].message
    assert (diagnostics[0].line, diagnostics[0].column) == (4, 1)
    assert diagnostics[0].measure == "2"
    selected = text.encode("utf-16-le")[
        diagnostics[0].start * 2 : diagnostics[0].end * 2
    ].decode("utf-16-le")
    assert selected == "2 2 2 2 2 & 0 2 2 2 |"


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
# 对应用例 A / B / C / G（见 docs/issues.md R7）。
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


def test_part_measure_count_mismatch_reports_first_missing_measure() -> None:
    # W1：多声部不一致警告应携带第一个缺失小节的显示号与文案提示。
    text = (
        '// @part 1 name="a"\n1=C\n4/4\n1 2 3 4 | 5 6 7 1 |\n'
        '// @part 2 name="b"\n1=C\n4/4\n1 2 3 4 |'
    )

    diagnostics = validate_jianpu_text(text)

    assert len(diagnostics) == 1
    assert diagnostics[0].measure == "2"
    assert "（b从第 2 小节起缺失）" in diagnostics[0].message


def test_part_measure_count_mismatch_uses_continuous_number_across_pages() -> None:
    # W1：第 1 页各声部 1 小节 → 第 2 页 base=2；左手缺 1 小节 → 第 3 小节起缺失。
    text = (
        '// @page 1 name="p1.png"\n'
        '// @part 1 name="右手"\n1=C\n4/4\n1 2 3 4 |\n'
        '// @part 2 name="左手"\n1=C\n4/4\n1 2 3 4 |\n'
        '// @page 2 name="p2.png"\n'
        '// @part 1 name="右手"\n1=C\n4/4\n1 2 3 4 | 5 6 7 1 |\n'
        '// @part 2 name="左手"\n1=C\n4/4\n1 2 3 4 |\n'
    )

    diagnostics = validate_jianpu_text(text, check_measure_durations=True)

    mismatch = [d for d in diagnostics if "各声部小节数量不一致" in d.message]
    assert len(mismatch) == 1
    assert mismatch[0].measure == "3"
    assert "（左手从第 3 小节起缺失）" in mismatch[0].message


def test_part_measure_count_mismatch_with_equal_span_has_no_measure_hint() -> None:
    # W1：反复结构使小节「数量」不同但占位相同（1 小节 ×2 vs 2 小节），
    # 不存在缺失小节，不填 measure、不追加提示。
    text = (
        '// @part 1 name="a"\n1=C\n4/4\n1 2 3 4 *2 |\n'
        '// @part 2 name="b"\n1=C\n4/4\n1 2 3 4 | 5 6 7 1 |\n'
    )

    diagnostics = validate_jianpu_text(text)

    mismatch = [d for d in diagnostics if "各声部小节数量不一致" in d.message]
    assert len(mismatch) == 1
    assert mismatch[0].measure is None
    assert "起缺失" not in mismatch[0].message


def test_lyric_measure_overflow_reports_first_orphan_measure() -> None:
    # W1：歌词小节数超过谱面时，measure 指向第一个无对应谱面的歌词小节。
    text = "1=C\n4/4\n1 2 3 4 |\n/L: 一 | 二 三/\n"

    diagnostics = validate_jianpu_text(text)

    overflow = [d for d in diagnostics if "歌词小节数不能超过谱面小节数" in d.message]
    assert len(overflow) == 1
    assert overflow[0].measure == "2"


def test_lyric_measure_overflow_uses_continuous_number_in_multi_page() -> None:
    # W1：多页文档歌词溢出，measure 为按页连续显示号（第 2 页 base=2，
    # 左手 1 小节 → 第一个溢出的歌词小节是显示号 3，而非段内局部号 2）。
    text = (
        '// @page 1 name="p1.png"\n'
        '// @part 1 name="右手"\n1=C\n4/4\n1 2 3 4 |\n'
        '// @part 2 name="左手"\n1=C\n4/4\n1 2 3 4 |\n'
        '// @page 2 name="p2.png"\n'
        '// @part 1 name="右手"\n1=C\n4/4\n1 2 3 4 |\n'
        '// @part 2 name="左手"\n1=C\n4/4\n1 2 3 4 |\n/L: 一 | 二/\n'
    )

    diagnostics = validate_jianpu_text(text, check_measure_durations=True)

    overflow = [d for d in diagnostics if "歌词小节数不能超过谱面小节数" in d.message]
    assert len(overflow) == 1
    assert overflow[0].measure == "3"


def test_round_two_part_errors_use_continuous_display_measure_numbers() -> None:
    # W1 顺带修复：第二轮按声部分段解析的 token 错误（掩码歌词块后暴露的
    # 非法字符）曾透传段内局部号；第 2 页 base=2，局部 2/3 → 显示号 3/4。
    text = (
        '// @page 1 name="p1.png"\n'
        '// @part 1 name="右手"\n1=C\n4/4\n1 2 3 4 |\n'
        '// @part 2 name="左手"\n1=C\n4/4\n1 2 3 4 |\n'
        '// @page 2 name="p2.png"\n'
        '// @part 1 name="右手"\n1=C\n4/4\n1 2 3 4 |\n'
        '// @part 2 name="左手"\n1=C\n4/4\n1 2 3 4 |\n/L: 一 | 二/\n'
    )

    diagnostics = validate_jianpu_text(text, check_measure_durations=True)
    errors = [d for d in diagnostics if "不支持的简谱 token" in d.message]

    assert [d.measure for d in errors] == ["3", "4"]


def test_structural_diagnostics_keep_measure_empty() -> None:
    # W1：标记格式/歌词块形状/文档头配置类错误属于结构级问题，保持 measure 为空。
    cases = [
        "1=C\n// @part 1\n1 2 3 4 |\n",  # 分谱标记格式无效
        "1=C\n4/4\n1 2 3 4 |\n/L: 歌词没有结束\n",  # 歌词块缺少结束符
        '// @part 1 name="a"\n1=C\n0/4\n1 2 3 4 |\n',  # 拍号无效
        '// @part 1 name="a"\n1=C\ninstrument=xyz\n1 2 3 4 |\n',  # instrument 无效
        "1=C\n4/4\n1 2 3 4 |\nL: 旧歌词语法\n",  # 旧 L: 语法
    ]

    for text in cases:
        diagnostics = validate_jianpu_text(text, check_measure_durations=True)
        assert diagnostics, text
        # 首条诊断即结构级错误本身；开启时值检查后，掩码可能暴露后续
        # 内容级 token 错误（携带小节号属正常），不在本用例断言范围内。
        assert diagnostics[0].measure is None, text
