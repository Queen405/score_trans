from __future__ import annotations

from fractions import Fraction
from trans_jp.models.melody import AttributeValue, NoteAttributes
from trans_jp.symbols.melody import derive_note_attributes, serialize_note


def note(**values):
    fields = {
        name: AttributeValue(value, "confirmed")
        for name, value in {
            "octave": 0,
            "accidental": "none",
            "underlines": 0,
            "dots": 0,
            "extensions": 0,
        }.items()
    }
    fields.update(
        {name: AttributeValue(value, "confirmed") for name, value in values.items()}
    )
    return NoteAttributes("r0000:c0000", "s0:r0:t0", "3", fields)


def test_fraction_duration_and_octave_serialization():
    n = derive_note_attributes(note(octave=-1, underlines=2, dots=1))
    assert n.duration == Fraction(3, 8)
    assert serialize_note(n) == "s3,."


def test_unknown_never_becomes_quarter_note():
    n = note()
    n.fields["underlines"] = AttributeValue(None, "unknown", reason="crop boundary")
    assert derive_note_attributes(n).duration is None
    assert serialize_note(n) is None


def test_mixed_extension_and_dot_scope_is_not_guessed():
    n = derive_note_attributes(note(dots=1, extensions=1))
    assert n.duration is None
    assert serialize_note(n) is None


def test_regular_extensions_use_exact_quarter_units():
    assert derive_note_attributes(note(extensions=3)).duration == 4


def test_rest_does_not_have_octave_or_accidental():
    n = note(octave=1)
    n.degree = "0"
    assert serialize_note(derive_note_attributes(n)) is None


def test_review_cannot_invent_geometry_or_share_dot():
    from pathlib import Path
    import json
    from trans_jp.models.geometry import Box
    from trans_jp.models.melody import AttachmentCandidate, AttachmentReviewRequest
    from trans_jp.recognition.attachment_reviewer import parse_attachment_review

    c = AttachmentCandidate(
        "a0", Box(10, 10, 3, 3), ("octave_up",), ("ink",), ("b0", "b1")
    )
    req = AttachmentReviewRequest(
        "request", Path("unused"), ("b0", "b1"), (c,), "digest"
    )
    result = parse_attachment_review(
        json.dumps(
            {
                "schema_version": 1,
                "relations": [
                    {
                        "candidate_id": "a0",
                        "body_ids": ["b0", "b1"],
                        "kind": "octave_up",
                    }
                ],
            }
        ),
        req,
    )
    assert not result.relations and result.unknown_ids == ["a0"]
    result = parse_attachment_review(
        json.dumps(
            {
                "schema_version": 1,
                "relations": [
                    {"candidate_id": "new", "body_ids": ["b0"], "kind": "octave_up"}
                ],
            }
        ),
        req,
    )
    assert result.status == "invalid"


def test_metadata_does_not_default_to_target_key():
    from trans_jp.recognition.attachment_reviewer import parse_melody_metadata
    import json

    assert parse_melody_metadata("{}", ("page",))["key"]["value"] is None
    data = {
        "schema_version": 1,
        "key": {"value": "Bb", "status": "confirmed", "region_id": "page"},
        "meter": {"value": "4/4", "status": "confirmed", "region_id": "page"},
    }
    result = parse_melody_metadata(json.dumps(data), ("page",))
    assert result["key"]["value"] == "Bb"
    assert result["key"]["status"] == "observed"
    data["key"]["region_id"] = "invented"
    assert parse_melody_metadata(json.dumps(data), ("page",))["key"]["value"] is None


def test_cropped_search_zone_never_confirms_zero_octave():
    from trans_jp.models.candidates import CandidateRegistry, LocatedCandidate
    from trans_jp.models.geometry import Box
    from trans_jp.matching.attachment_relations import attributes_for_body

    c = LocatedCandidate("b0", "digit", Box(80, 1, 20, 30), (0,), ())
    reg = CandidateRegistry(0, 200, 50, (c,))
    n = attributes_for_body("b0", "s0:r0:t0", "3", reg, (), [])
    assert n.fields["octave"].status == "unknown"
    assert n.fields["underlines"].value is None


def test_shared_underlines_merge_fragments_without_duplicate_levels():
    from trans_jp.models.candidates import CandidateRegistry, LocatedCandidate
    from trans_jp.models.geometry import Box
    from trans_jp.models.melody import AttachmentCandidate, AttachmentRelation
    from trans_jp.matching.attachment_relations import attributes_for_body

    c = LocatedCandidate("b0", "digit", Box(100, 100, 20, 30), (0,), ())
    reg = CandidateRegistry(0, 400, 300, (c,))
    marks = tuple(
        AttachmentCandidate(
            f"a{i}", Box(90, 135 + dy, 40, 2), ("underline",), (), ("b0",)
        )
        for i, dy in enumerate((0, 1, 8))
    )
    relations = [
        AttachmentRelation(m.candidate_id, ("b0",), "underline") for m in marks
    ]
    n = attributes_for_body("b0", "s0:r0:t0", "3", reg, marks, relations)
    assert n.fields["underlines"].value == 2
    assert derive_note_attributes(n).duration == Fraction(1, 4)


def test_attachment_review_http_attempt_budget(monkeypatch):
    import httpx
    from trans_jp.recognition.llm_client import LlmClient
    from trans_jp.models.contracts import LlmConfig, CompletionResult

    client = LlmClient(LlmConfig("key", "http://test", "test"), "")
    monkeypatch.setattr(
        "trans_jp.recognition.llm_client.time.sleep", lambda seconds: None
    )
    calls = []

    def clipped(prompt):
        calls.append(prompt)
        return CompletionResult("{}", "length")

    result = client._review_retry(clipped, "test")
    assert len(calls) == 3 and result.finish_reason == "length"
    calls.clear()

    def denied(prompt):
        calls.append(prompt)
        request = httpx.Request("POST", "http://test")
        raise httpx.HTTPStatusError(
            "401", request=request, response=httpx.Response(401, request=request)
        )

    import pytest

    with pytest.raises(httpx.HTTPStatusError):
        client._review_retry(denied, "test")
    assert len(calls) == 1


def test_unsupported_music_mark_is_not_treated_as_absent():
    from trans_jp.models.candidates import CandidateRegistry, LocatedCandidate
    from trans_jp.models.geometry import Box
    from trans_jp.models.melody import AttachmentCandidate, AttachmentRelation
    from trans_jp.matching.attachment_relations import attributes_for_body

    c = LocatedCandidate("b0", "digit", Box(100, 100, 20, 30), (0,), ())
    a = AttachmentCandidate("a0", Box(95, 80, 25, 10), ("unclassified",), (), ("b0",))
    n = attributes_for_body(
        "b0",
        "s0:r0:t0",
        "3",
        CandidateRegistry(0, 400, 300, (c,)),
        (a,),
        [AttachmentRelation("a0", ("b0",), "unsupported", source="vlm")],
    )
    assert all(f.status == "unsupported" for f in n.fields.values())
    assert derive_note_attributes(n).duration is None


def test_local_metadata_requires_visible_declaration_and_existing_region():
    import json
    from trans_jp.recognition.attachment_reviewer import parse_local_metadata

    data = {
        "schema_version": 1,
        "declarations": [
            {"region_id": "meta0000", "key_text": "1=#C", "meter_text": "4/4"},
            {"region_id": "invented", "key_text": "1=F", "meter_text": None},
        ],
    }
    result = parse_local_metadata(json.dumps(data), ("meta0000",))
    assert len(result) == 1
    assert result[0]["key"] == "C#" and result[0]["meter"] == "4/4"
    assert result[0]["status"] == "observed_local"
    data["declarations"][0]["key_text"] = "F#"
    assert parse_local_metadata(json.dumps(data), ("meta0000",))[0]["key"] is None


def test_metadata_region_proposals_have_measured_bounds():
    import numpy as np
    from trans_jp.structure.metadata_regions import detect_metadata_regions

    binary = np.full((120, 300), 255, dtype=np.uint8)
    binary[50:52, 100:112] = 0
    binary[58:60, 100:112] = 0
    regions = detect_metadata_regions(binary)
    assert regions
    assert regions[0].x < 100 < regions[0].right
    assert regions[0].y < 50 < regions[0].bottom
