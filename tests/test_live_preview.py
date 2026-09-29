from __future__ import annotations

from dataclasses import asdict
from fractions import Fraction

import pytest

from score_trans.domain.parse.live_jianpu import select_live_measure

from score_trans.domain.parse.jianpu_text import JianpuSyntaxError, parse_jianpu_score
from score_trans.services.render.main import render_live_measure_svg


def nine_measures() -> str:
    bars = ["1 2 3 4"] * 9
    bars[6] = "1 2 INVALID 4"
    return "1=C\n4/4\n" + " |\n".join(bars) + " |"


def test_other_measure_error_does_not_block_cursor_measure() -> None:
    text = nine_measures()
    svg = render_live_measure_svg(text, text.rindex("1 2 3 4"))
    assert "<svg" in svg


def test_current_measure_error_still_fails() -> None:
    text = nine_measures()
    with pytest.raises(JianpuSyntaxError, match="INVALID"):
        render_live_measure_svg(text, text.index("INVALID"))


def select(text: str, needle: str, **kwargs):
    cursor = len(text[: text.rindex(needle)].encode("utf-16-le")) // 2
    return select_live_measure(text, cursor, **kwargs)


@pytest.mark.parametrize(
    "broken", ["INVALID", "[1+3", "$123", "& 1", "1 &", "w1 2 & w6,"]
)
def test_recovery_stops_at_bar_and_rejects_broken_measure(broken: str) -> None:
    text = f"1=C\n4/4\n{broken} | 5 6 7 1 |"
    result = select(text, "5 6")
    assert result.initial_measure_number == 2
    assert result.score.measures[0].events[0].pitches[0].degree == 5
    with pytest.raises(JianpuSyntaxError):
        select(text, broken)
    with pytest.raises(JianpuSyntaxError):
        parse_jianpu_score(text)


@pytest.mark.parametrize(
    "broken,restored,field,expected",
    [
        ("1=X", "1=G", "target_key", "F"),
        ("0/4", "3/4", "beats_per_measure", 4),
        ("tempo=bad", "tempo=90", "tempo", 80),
    ],
)
def test_invalid_context_uses_last_valid_value_and_warning_clears(
    broken, restored, field, expected
) -> None:
    text = f"1=F\n4/4\ntempo=80\n1 2 3 4 |\n{broken}\n1 2 3 4 | 5 6 7 1 | {restored} 2 3 4 |"
    fallback = select(text, "5 6")
    assert getattr(fallback.score.measures[0], field) == expected
    assert len(fallback.warnings) == 1
    assert fallback.warnings[0].start == text.index(broken)
    assert select(text, "2 3 4 |").warnings == []
    with pytest.raises(JianpuSyntaxError):
        select(text, broken)


@pytest.mark.parametrize(
    "body",
    [
        "1 2 3 4 | 5 6 7 1 |",
        "|: 1 2 3 4 :| |: 5 6 7 1 :|",
        "1 2 3 4 || | 5 6 7 1 |",
        "*3 1 2 3 4 | 5 6 7 1 |",
        "|: 1 2 3 4 :| *2 | 5 6 7 1 |",
        "(1 2 3 4 | 5 6 7 1) |",
        "1~ 2 3 4~ | 4 5 6 7 |",
        "1 2 3 4 ^lh | 5 6 7 1 |",
        "w1 & 2 3 4 5 | w6, & 1 2 3 4 |",
        "1 2 3 4 | 1=G 3/4 tempo=90 5 6 7 |",
        "$123$ 4 5 6 | 1 2 3 4 |",
        "1 2 3 4 | 5 6 7 1 |\n/L: do re mi fa | so la ti do/",
    ],
)
def test_valid_measures_match_strict_parser(body: str) -> None:
    text = "1=C\n4/4\n" + body
    strict = parse_jianpu_score(text)
    for original in strict.measures:
        result = select_live_measure(text, original.source_start_utf16)
        assert asdict(result.score.measures[0]) == asdict(original)
        assert result.warnings == []


def test_failed_voice_is_discarded_and_cannot_leak_tie() -> None:
    text = "1=C\n4/4\nw1~ & INVALID | w5 |"
    result = select(text, "w5")
    assert len(result.score.measures[0].events) == 1
    assert not result.score.measures[0].events[0].tie_stop


def test_uncertain_lyrics_omitted_only_after_error() -> None:
    text = "1=C\n4/4\n1 2 3 4 | INVALID | 5 6 7 1 |\n/L: do re mi fa | so la ti do/"
    assert select(text, "1 2").score.measures[0].events[0].lyric == "do"
    result = select(text, "5 6")
    assert all(event.lyric is None for event in result.score.measures[0].events)
    assert any("歌词" in warning.message for warning in result.warnings)


def test_utf16_offsets_with_crlf_bom_comments_and_parts() -> None:
    text = '\ufeff// @page 1 name="🎵.png"\r\n// @part 1 name="高音🎻"\r\n1=C\r\n4/4\r\nINVALID |\r\n// @part 2 name="低音"\r\n1=C\r\n4/4\r\nw6, & 1 2 3 4 | // 忽略 | :|\r\n'
    result = select(text, "w6,")
    assert result.score.part_name == "低音"
    assert result.initial_measure_number == 1
    assert len(result.score.measures[0].events) == 5
    with pytest.raises(JianpuSyntaxError) as captured:
        select(text, "INVALID")
    assert (
        captured.value.token.start_utf16
        == len(text[: text.index("INVALID")].encode("utf-16-le")) // 2
    )


def test_pages_keep_numbering_and_independent_context() -> None:
    text = '// @page 1\n// @part 1 name="A"\n1=F\n3/4\ntempo=80\n*3 INVALID |\n// @page 2\n// @part 1 name="A"\n1=C\n4/4\nw5 |'
    result = select(text, "w5", initial_measure_number=10)
    assert result.initial_measure_number == 13
    assert result.score.measures[0].duration == Fraction(4)
    assert result.score.measures[0].tempo == 120


def test_errors_after_target_do_not_affect_it() -> None:
    text = "1=C\n4/4\nw1 |\ntempo=bad\nINVALID & |"
    assert select(text, "w1").warnings == []


@pytest.mark.parametrize("text", ["1=C\n4/4", "title=测试", "// comment", ""])
def test_header_only_input_does_not_crash(text: str) -> None:
    assert "<svg" in render_live_measure_svg(text, len(text))


def test_instrument_warning_clears_with_later_valid_setting() -> None:
    text = "instrument=guzheng\n1=C\n4/4\nw1 |\ninstrument=bad\nw2 | w3 |\ninstrument=general\nw4 |"
    result = select(text, "w3")
    assert result.score.instrument_profile == "guzheng"
    assert any("乐器" in w.message for w in result.warnings)
    result = select(text, "w4")
    assert result.score.instrument_profile == "general"
    assert result.warnings == []


def test_missing_connection_origin_after_error_is_reported() -> None:
    text = "1=C\n4/4\n(1 INVALID | 5 6 7 1) | w2 |"
    with pytest.raises(JianpuSyntaxError, match="起点不可确定"):
        select(text, "5 6")
    assert select(text, "w2").score.measures[0].events[0].pitches[0].degree == 2


def test_failed_slide_does_not_mutate_previous_successful_measure() -> None:
    text = "1=C\n4/4\nw1 | ^lh 2 INVALID | w3 |"
    result = select(text, "w1")
    event = result.score.measures[0].events[0]
    assert not event.slide_start
    assert event.slide_direction is None


@pytest.mark.parametrize(
    "broken_marker",
    ['// @part name="坏掉"', '// @page wrong\n// @part 1 name="A"', "// @page 2"],
)
def test_marker_damage_is_local_and_later_page_recovers(broken_marker: str) -> None:
    text = (
        '// @page 1\n// @part 1 name="A"\n1=C\n4/4\nw1 |\n'
        + broken_marker
        + '\n1=C\n4/4\nw2 |\n// @page 3\n// @part 1 name="A"\n1=C\n4/4\nw3 |'
    )
    assert select(text, "w1").score.measures[0].events[0].pitches[0].degree == 1
    with pytest.raises(JianpuSyntaxError, match="标记"):
        select(text, "w2")
    assert select(text, "w3").score.measures[0].events[0].pitches[0].degree == 3


def test_invalid_page_marker_in_single_part_document_is_not_silently_ignored() -> None:
    text = "// @page 1\n1=C\n4/4\nw1 |\n// @page wrong\nw2 |\n// @page 3\nw3 |"
    with pytest.raises(JianpuSyntaxError, match="分页标记"):
        select(text, "w2")
    assert select(text, "w3").score.measures[0].events[0].pitches[0].degree == 3


def test_live_api_keeps_existing_error_contract_and_adds_context_warnings() -> None:
    from fastapi.testclient import TestClient
    from score_trans.api.app import create_app

    client = TestClient(create_app(auth_disabled=True))
    text = "1=F\n4/4\nw1 | 1=X w2 | w3 |"
    successful = client.post(
        "/render/jianpu-live-svg",
        json={"jianpu_text": text, "cursor_offset": text.index("w3")},
    )
    assert successful.status_code == 200
    data = successful.json()
    assert "<svg" in data["svg"]
    assert data["jianpu_text"] == text
    assert data["warnings"][0]["severity"] == "warning"
    invalid = client.post(
        "/render/jianpu-live-svg",
        json={"jianpu_text": text, "cursor_offset": text.index("w2")},
    )
    assert invalid.status_code == 400
    assert invalid.json()["code"] == "jianpu_syntax"
    strict = client.post("/render/jianpu-live-svg", json={"jianpu_text": text})
    assert strict.status_code == 400


def _lyrics_of(selection) -> list[str | None]:
    return [event.lyric for event in selection.score.measures[0].events]


def test_cursor_in_lyric_block_selects_corresponding_measure() -> None:
    text = "1 | 2 | 3 | 4 | 5 |\n/L: 一 | 二 | 三 /\n"
    selection = select_live_measure(text, text.index("二"))
    assert selection.initial_measure_number == 2
    assert _lyrics_of(selection) == ["二"]


def test_unterminated_lyric_block_still_renders_with_lyrics() -> None:
    text = "1 2 3 4 | 5 6 7 1 |\n/L: 春 眠 | 晓"
    selection = select_live_measure(text, len(text))
    assert selection.initial_measure_number == 2
    assert _lyrics_of(selection)[0] == "晓"


def test_lyric_content_error_degrades_to_measure_without_lyrics() -> None:
    text = "1 | 2 | 3 |\n/L: 一 & 二 | 三 /\n"
    selection = select_live_measure(text, text.index("三"))
    assert selection.initial_measure_number == 2
    assert _lyrics_of(selection) == [None]


def test_lyric_overflow_clamps_to_last_measure() -> None:
    text = "1 | 2 |\n/L: 一 | 二 | 三 /\n"
    selection = select_live_measure(text, text.index("三"))
    assert selection.initial_measure_number == 2


def test_broken_lyric_block_does_not_kill_body_cursor_preview() -> None:
    text = "1 2 3 4 | 5 6 7 1 |\n/L: 春 眠 | 晓"
    selection = select_live_measure(text, text.index("1"))
    assert selection.initial_measure_number == 1


def test_lyric_cursor_uses_repeat_weighted_measure_number() -> None:
    text = "1 2 3 4 *2 | 5 6 7 1 *3 |\n/L: 一 二 三 四 | 五 六 七 一/\n"
    selection = select_live_measure(text, text.index("五"))
    assert selection.initial_measure_number == 3
    assert _lyrics_of(selection) == ["五", "六", "七", "一"]


def test_multiline_lyric_block_cursor_maps_by_bar_count() -> None:
    text = "1 | 2 | 3 |\n/L: 一 |\n二 | 三 /\n"
    selection = select_live_measure(text, text.index("三"))
    assert selection.initial_measure_number == 3
    assert _lyrics_of(selection) == ["三"]
