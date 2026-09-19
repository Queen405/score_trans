from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
import pytest
from trans_jp.models.contracts import CliConfig, LlmConfig, CompletionResult, RowSegment
from trans_jp.models.candidates import CandidateRegistry, LocatedCandidate
from trans_jp.models.classification import CandidateBatchResult, CandidateClassification
from trans_jp.models.geometry import Box, Transform
from trans_jp.models.lyrics import LyricsResult, TextRequest, TextRegion
from trans_jp.recognition.lyrics import parse_text_response
from trans_jp.structure.lyric_regions import find_text_regions, word_boxes
from trans_jp.matching.text_conflicts import body_text_conflicts
from trans_jp.structure.body_assembler import assemble_body_tokens
from trans_jp.pipeline.runner import run
from trans_jp.io.output_writer import write_outputs
from trans_jp.models.errors import EngineError


def test_strict_text_response():
    request = TextRequest(
        "q", Path("unused"), ({"id": "a"}, {"id": "b"}), "regions", "hash"
    )
    response = CompletionResult(
        json.dumps(
            {
                "schema_version": 1,
                "items": [
                    {"id": "a", "role": "lyrics", "text": "春"},
                    {"id": "a", "role": "notation", "text": ""},
                    {"id": "b", "role": "lyrics", "text": None},
                ],
            }
        )
    )
    result = parse_text_response(response, request)
    assert all(r["role"] == "unknown" for r in result)
    assert all(
        r["role"] == "unknown"
        for r in parse_text_response(
            CompletionResult(response.content, "length"), request
        )
    )
    assert all(
        r["role"] == "unknown"
        for r in parse_text_response(CompletionResult("plain lyrics"), request)
    )


def test_boxes_are_ink_not_equal_width():
    image = np.full((40, 100), 255, np.uint8)
    image[5:25, 5:14] = 0
    image[5:25, 16:20] = 0  # disconnected radical belonging to first character
    image[5:25, 45:76] = 0
    region = TextRegion("line", Box(0, 0, 100, 40), Box(0, 0, 100, 40))
    boxes = word_boxes(image, region, "春天")
    assert boxes == [Box(5, 5, 15, 20), Box(45, 5, 31, 20)]
    tr = Transform(2, 2, 0.05, 3)
    regions = find_text_regions(image, tr)
    assert regions
    assert all(r.bounds == tr.box(r.bounds_work) for r in regions)


def test_text_gate_excludes_accepted_labels_but_not_nearby_music(tmp_path):
    row = RowSegment(0, 0, 60, tmp_path / "row.png", 100, 60)
    note = LocatedCandidate("n", "digit", Box(10, 5, 10, 15), (0,), ("a",))
    text = LocatedCandidate("line", "digit", Box(10, 30, 10, 15), (1,), ("b",))
    registry = CandidateRegistry(0, 100, 60, (note, text))
    result = LyricsResult(
        version=3,
        regions=[
            {"id": "a", "role": "notation", "bounds_work": asdict(Box(5, 4, 30, 17))},
            {"id": "b", "role": "lyrics", "bounds_work": asdict(Box(5, 29, 30, 17))},
        ],
    )
    blocked = body_text_conflicts([row], [registry], result)
    assert blocked == {"line": "text_excluded"}
    batch = CandidateBatchResult(
        "batch",
        registry.digest,
        [
            CandidateClassification(c.candidate_id, "3", "digit", 0.9, "recognized")
            for c in registry.candidates
        ],
    )
    assembled = assemble_body_tokens(registry, [batch], row, blocked=blocked)
    assert [t.candidate_ids for t in assembled.tokens] == [("n",)]
    result.regions[1]["role"] = "unknown"
    assert body_text_conflicts([row], [registry], result) == {
        "line": "text_music_conflict"
    }


class FakeText:
    calls = 0
    fail = False

    def __init__(self, config):
        pass

    def recognize_text(self, request):
        type(self).calls += 1
        if self.fail:
            raise TimeoutError("simulated")
        items = []
        for item in request.items:
            if request.task == "words":
                text = "春" if item["id"].endswith("000") else "天"
                role = "unknown"
            else:
                lyric = item["bounds_work"]["y"] > 40
                text = "春天" if lyric else ""
                role = "lyrics" if lyric else "notation"
            items.append({"id": item["id"], "role": role, "text": text})
        return CompletionResult(
            json.dumps({"schema_version": 1, "items": items}, ensure_ascii=False)
        )


class FakeBodies:
    ids = []

    def classify(self, request):
        type(self).ids.extend(request.candidate_ids)
        by_id = {c.candidate_id: c for c in request.registry.candidates}
        items = [
            {
                "candidate_id": cid,
                "label": "barline" if by_id[cid].kind == "barline" else "3",
                "kind": by_id[cid].kind,
                "status": "recognized",
            }
            for cid in request.candidate_ids
        ]
        return CompletionResult(json.dumps({"schema_version": 3, "items": items}))


def scene(tmp_path):
    image = Image.new("RGB", (200, 120), "white")
    d = ImageDraw.Draw(image)
    for y in (10, 65):
        d.rectangle((15, y, 24, y + 20), fill="black")
        d.rectangle((50, y, 65, y + 20), fill="black")
    p = tmp_path / "score.png"
    image.save(p)
    return p


def test_pipeline_filters_before_request_and_replays_without_network(
    tmp_path, monkeypatch
):
    import trans_jp.pipeline.runner as runner

    monkeypatch.setattr(runner, "ConfiguredTextRecognizer", FakeText)
    FakeText.calls = 0
    FakeText.fail = False
    FakeBodies.ids = []
    p = scene(tmp_path)
    config = CliConfig(
        p,
        tmp_path / "online",
        LlmConfig("test", "test", "test"),
        min_image_edge=0,
        lyrics_mode="recognize",
        debug=True,
    )
    result = run(config, FakeBodies())
    write_outputs(result, config.output_dir)
    assert result.lyrics["lines"]
    assert len(result.lyrics["lines"][0]["tokens"]) == 2
    blocked = {c["candidate_id"] for c in result.lyrics["conflicts"]}
    assert blocked and not blocked.intersection(FakeBodies.ids)
    assert all(
        not blocked.intersection(t.candidate_ids) for r in result.rows for t in r.tokens
    )
    first_calls = FakeText.calls
    replay = run(
        CliConfig(
            p,
            tmp_path / "replay",
            LlmConfig("", "", ""),
            min_image_edge=0,
            body_responses_dir=config.output_dir / "rows",
            melody_review=False,
        )
    )
    assert FakeText.calls == first_calls
    assert replay.lyrics == result.lyrics
    assert replay.overlay_svg == result.overlay_svg
    assert (config.output_dir / "lyrics.txt").read_text(encoding="utf-8") == "春天"
    # Removing the marker must not silently downgrade to unfiltered v3 replay.
    manifest = config.output_dir / "manifest.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data.pop("lyrics")
    manifest.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(EngineError, match="回放"):
        run(
            CliConfig(
                p,
                tmp_path / "tampered",
                LlmConfig("", "", ""),
                min_image_edge=0,
                body_responses_dir=config.output_dir / "rows",
            )
        )


def test_failure_is_not_absence_of_text(tmp_path, monkeypatch):
    import trans_jp.pipeline.runner as runner

    monkeypatch.setattr(runner, "ConfiguredTextRecognizer", FakeText)
    FakeText.fail = True
    FakeBodies.ids = []
    try:
        result = run(
            CliConfig(
                scene(tmp_path),
                tmp_path / "out",
                LlmConfig("test", "test", "test"),
                min_image_edge=0,
                lyrics_mode="recognize",
            ),
            FakeBodies(),
        )
        assert not FakeBodies.ids
        assert not any(r.tokens for r in result.rows)
        assert result.lyrics["warnings"] and result.lyrics["conflicts"]
    finally:
        FakeText.fail = False


def test_unique_alignment_does_not_guess_repeated_or_missing_words():
    from trans_jp.matching.text_conflicts import unique_word_alignment

    assert unique_word_alignment(
        ["双", None, "过", "万"], ["双", "双", "飞", "过", "万"]
    ) == {2: 3, 3: 4}
    assert unique_word_alignment(["无", "言"], ["无", "言"]) == {0: 0, 1: 1}
    assert unique_word_alignment(["love", "love"], ["love"]) == {}
    assert unique_word_alignment(["I", None, "you"], ["I", "love", "you"]) == {
        0: 0,
        2: 2,
    }


def test_chinese_adjacent_full_characters_do_not_merge():
    image = np.full((40, 100), 255, np.uint8)
    image[0:40, 0:37] = 0
    image[0:40, 44:82] = 0
    region = TextRegion("line", Box(0, 0, 100, 40), Box(0, 0, 100, 40))
    assert len(word_boxes(image, region, "默说")) == 2


def test_text_preview_escapes_model_text_and_javascript():
    from trans_jp.models.lyrics import LyricLine
    from trans_jp.rendering.lyrics import lyric_overlay, lyrics_preview

    text = "</script><script>alert(1)</script>"
    b = Box(0, 0, 10, 10)
    r = LyricsResult(lines=[LyricLine("line", text, b, b, "en")])
    svg = lyric_overlay(r, 100, 100)
    html = lyrics_preview("data:image/png;base64,", "", svg, r, 100, 100)
    assert text not in html
    assert html.count("<script>") == 1 and html.count("</script>") == 1
    assert "\u003c/script>" in html


def test_english_word_boxes_and_punctuation():
    from trans_jp.structure.lyric_regions import text_units

    assert text_units("I love you, don't go.") == ["I", "love", "you,", "don't", "go."]
    image = np.full((25, 140), 255, np.uint8)
    for left, right in [(5, 8), (10, 14), (16, 19), (45, 49), (52, 57), (59, 64)]:
        image[4:20, left:right] = 0
    region = TextRegion("line", Box(0, 0, 140, 25), Box(0, 0, 140, 25))
    boxes = word_boxes(image, region, "the sun")
    assert boxes == [Box(5, 4, 14, 16), Box(45, 4, 19, 16)]


def test_source_bound_evidence_cannot_escape_replay_root(tmp_path):
    from trans_jp.io.lyrics_artifacts import (
        write_lyrics_manifest,
        validate_lyrics_replay,
    )

    binding = {"source_sha256": "s", "min_image_edge": 0, "rows": []}
    write_lyrics_manifest(tmp_path, binding, {"version": 4, "lines": []})
    file = tmp_path / "lyrics-manifest.json"
    m = json.loads(file.read_text(encoding="utf-8"))
    m["files"]["../outside"] = "invalid"
    file.write_text(json.dumps(m), encoding="utf-8")
    with pytest.raises(ValueError):
        validate_lyrics_replay(tmp_path, binding)


@pytest.mark.parametrize("name", ["image", "image copy 10"])
def test_frozen_real_pages_no_network_and_filter_preserves_known_music(
    name, tmp_path, monkeypatch
):
    import hashlib
    import trans_jp.pipeline.runner as runner

    root = Path(__file__).parents[1]
    fixture = json.loads(
        (root / "tests/fixtures/lyrics/frozen_development.json").read_text(
            encoding="utf-8"
        )
    )["pages"][name]
    source = root / "examples" / f"{name}.png"
    assert hashlib.sha256(source.read_bytes()).hexdigest() == fixture["source_sha256"]

    class FrozenText:
        def __init__(self, config):
            pass

        def recognize_text(self, request):
            data = fixture["text"][request.request_id]
            assert data["sha256"] == request.sha256
            response = data["response"]
            if response["failure"]:
                raise RuntimeError("frozen failure")
            return CompletionResult(response["content"], response["finish_reason"])

    class FrozenBodies:
        def classify(self, request):
            data = fixture["bodies"][request.batch_id]
            assert data["registry_sha256"] == request.registry.digest
            return CompletionResult(data["response"], data["finish_reason"])

    legacy_recognize = runner.recognize_lyrics

    def legacy(*args, **kwargs):
        return legacy_recognize(*args, **kwargs, version=3)

    monkeypatch.setattr(runner, "recognize_lyrics", legacy)
    monkeypatch.setattr(runner, "ConfiguredTextRecognizer", FrozenText)
    config = CliConfig(
        source,
        tmp_path / name,
        LlmConfig("fake", "fake", "fake"),
        lyrics_mode="recognize",
        debug=True,
    )
    result = run(config, FrozenBodies())
    if name == "image":
        truth = json.loads(
            (root / "tests/fixtures/lyrics/liangzhu.json").read_text(encoding="utf-8")
        )
        primitives = [
            p for row in result.rows for t in row.tokens for p in t.geometry.primitives
        ]

        def within(b, zone):
            x, y, w, h = zone
            return x <= b.cx < x + w and y <= b.cy < y + h

        assert not any(
            within(p.bounds, r["box"]) for p in primitives for r in truth["lyrics"]
        )
        assert (
            sum(
                p.kind == "glyph"
                and any(within(p.bounds, b) for b in truth["music_bands"])
                for p in primitives
            )
            == 120
        )
        assert sum(len(line["tokens"]) for line in result.lyrics["lines"]) == 43
    else:
        labels = json.loads(
            (root / "tests/fixtures/coordinates/reviewed_bodies.json").read_text(
                encoding="utf-8"
            )
        )
        expected = [r for r in labels["rows"] if r["image"] == name + ".png"]
        # The independently reviewed subset retains 123 emitted bodies; other
        # regions include a recorded request failure and must remain unresolved.
        rows = {r.row.index: r for r in result.rows}
        emitted = 0
        for ref in expected:
            row = rows[ref["row_index"]]
            emitted += sum(
                p.kind == "glyph" or p.value == "barline"
                for t in row.tokens
                for p in t.geometry.primitives
            )
        assert emitted == 123
        assert any(r["status"] == "failed" for r in result.lyrics["regions"])
