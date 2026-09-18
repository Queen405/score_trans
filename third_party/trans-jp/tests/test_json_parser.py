from __future__ import annotations

import json

from trans_jp.json_parser import parse_row_response


def test_parse_plain_json():
    content = json.dumps(
        {
            "row_type": "notation",
            "row_text": "1 2 |",
            "tokens": [
                {"text": "1", "x": 0.1, "w": 0.05, "role": "note"},
                {"text": "|", "x": 0.3, "w": 0.02, "role": "barline"},
            ],
            "warnings": [],
            "confidence": 0.9,
        }
    )
    result = parse_row_response(content)
    assert result["row_type"] == "notation"
    assert result["row_text"] == "1 2 |"
    assert len(result["tokens"]) == 2
    assert result["tokens"][0]["x"] == 0.1
    assert result["confidence"] == 0.9


def test_parse_markdown_fenced_json():
    content = '```json\n{"row_text": "1 2 |", "tokens": []}\n```'
    result = parse_row_response(content)
    assert result["row_text"] == "1 2 |"


def test_parse_json_with_surrounding_text():
    content = '好的，识别结果如下：\n{"row_text": "1 |", "tokens": []}\n完毕。'
    result = parse_row_response(content)
    assert result["row_text"] == "1 |"


def test_parse_truncated_json_repaired():
    content = '{"row_text": "1 2 |", "tokens": [{"text": "1", "x": 0.1, "w": 0.05, "role": "note"'
    result = parse_row_response(content)
    assert result["row_text"] == "1 2 |"


def test_parse_garbage_returns_defaults():
    result = parse_row_response("完全不是 JSON")
    assert result["row_text"] == ""
    assert result["tokens"] == []
    assert any("JSON 解析失败" in w for w in result["warnings"])


def test_missing_fields_filled_with_defaults():
    result = parse_row_response("{}")
    assert result["row_type"] == "notation"
    assert result["key"] is None
    assert result["meter"] is None
    assert result["row_text"] == ""
    assert result["tokens"] == []
    assert any("缺少字段" in w for w in result["warnings"])


def test_invalid_row_type_falls_back():
    result = parse_row_response('{"row_type": "weird", "row_text": "x", "tokens": []}')
    assert result["row_type"] == "notation"


def test_invalid_positions_preserved_without_clamping():
    content = json.dumps(
        {
            "row_text": "1 2 |",
            "tokens": [
                {"text": "1", "x": -0.5, "w": 2.0, "role": "note"},
                {"text": "|", "x": 0.95, "w": 0.5, "role": "barline"},
            ],
        }
    )
    result = parse_row_response(content)
    t0, t1 = result["tokens"]
    assert (t0["x"], t0["w"]) == (-0.5, 2.0)
    assert (t1["x"], t1["w"]) == (0.95, 0.5)
    assert any("无效" in w for w in result["warnings"])


def test_missing_positions_remain_unknown():
    content = json.dumps(
        {
            "row_text": "1 2 3 |",
            "tokens": [
                {"text": "1", "role": "note"},
                {"text": "2", "role": "note"},
                {"text": "3", "role": "note"},
                {"text": "|", "role": "barline"},
            ],
        }
    )
    result = parse_row_response(content)
    xs = [t["x"] for t in result["tokens"]]
    assert xs == [None] * 4
    assert all(t["w"] is None for t in result["tokens"])
    assert any("未补位" in w for w in result["warnings"])


def test_tokens_non_list_ignored():
    result = parse_row_response('{"row_text": "1 |", "tokens": "oops"}')
    assert result["tokens"] == []


def test_tokens_without_text_dropped():
    content = json.dumps(
        {
            "row_text": "1 |",
            "tokens": [
                {"text": "", "x": 0.1, "w": 0.1},
                {"x": 0.2, "w": 0.1},
                {"text": "1", "x": 0.1, "w": 0.05, "role": "note"},
            ],
        }
    )
    result = parse_row_response(content)
    assert len(result["tokens"]) == 1
    assert result["tokens"][0]["text"] == "1"


def test_optional_y_h_preserve_original_values():
    content = json.dumps(
        {
            "row_text": "1 |",
            "tokens": [
                {"text": "1", "x": 0.1, "w": 0.05, "role": "note", "y": 1.5, "h": -1}
            ],
        }
    )
    result = parse_row_response(content)
    token = result["tokens"][0]
    assert token["y"] == 1.5
    assert token["h"] == -1


def test_narrow_barline_is_not_expanded_to_one_percent():
    data = parse_row_response(
        json.dumps({"row_text": "|", "tokens": [{"text": "|", "x": 0.5, "w": 0.001}]})
    )
    assert data["tokens"][0]["w"] == 0.001


def test_nonfinite_model_numbers_are_not_serialized_as_nan():
    data = parse_row_response(
        '{"row_text":"1","confidence":NaN,"tokens":[{"text":"1","x":NaN,"w":Infinity}]}'
    )
    assert data["tokens"][0]["x"] is None
    assert data["confidence"] is None
    json.dumps(data, allow_nan=False)
