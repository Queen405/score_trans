from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path
import struct

import score_trans.domain.write.jianpu_text as jianpu_writer
from score_trans.domain.parse.jianpu_text import parse_jianpu_score
from score_trans.domain.parse.musicxml import musicxml_to_score
from score_trans.domain.provenance import apply_text_anchors
from score_trans.domain.write.jianpu_text import score_to_jianpu_document
from score_trans.exec.render.actions import _tag_score_source_page
from score_trans.models.history.entities import HistoryPage
from score_trans.models.provenance.schemas import TextAnchor
from score_trans.models.score import Event, JianpuPitch, JianpuScore, Measure
from score_trans.services.overlay.overlay_service import OverlayService
from score_trans.services.history.history_service import HistoryService
from score_trans.services.render.engraving.renderer import PublicationRenderer
from score_trans.services.render.main import render_score_svg


def _unmarked_sextuplet_musicxml(group_count: int = 4) -> str:
    notes: list[str] = []
    for index in range(group_count * 6):
        position = index % 6
        beam_status = (
            "begin" if position == 0 else "end" if position == 5 else "continue"
        )
        dotted = index == 3
        notes.append(
            f"""
            <note id="st__n-s1-i{100 + index}">
              <pitch><step>{"B" if position in {0, 4} else "A"}</step><octave>4</octave></pitch>
              <duration>{9 if dotted else 6}</duration>
              <voice>1</voice><type>16th</type>{"<dot/>" if dotted else ""}
              <beam number="1">{beam_status}</beam>
              <beam number="2">{beam_status}</beam>
            </note>
            """
        )
    return f"""
    <score-partwise version="4.0">
      <part-list><score-part id="P1"><part-name>Music</part-name></score-part></part-list>
      <part id="P1"><measure number="1">
        <attributes>
          <divisions>24</divisions>
          <key><fifths>0</fifths></key>
          <time><beats>4</beats><beat-type>4</beat-type></time>
        </attributes>
        {"".join(notes)}
      </measure></part>
    </score-partwise>
    """


def test_partial_six_note_beam_pattern_is_not_inferred_as_sextuplet() -> None:
    score = musicxml_to_score(_unmarked_sextuplet_musicxml(group_count=1))

    assert all(event.tuplet_count is None for event in score.measures[0].events)


def test_unmarked_complete_sextuplet_beams_restore_text_render_and_provenance() -> None:
    score = musicxml_to_score(_unmarked_sextuplet_musicxml())
    events = score.measures[0].events
    document = score_to_jianpu_document(score)
    svg = render_score_svg(score)

    group_ids = [event.tuplet_id for event in events]
    assert len(events) == 24
    assert all(event.duration == Fraction(1, 6) for event in events)
    assert all(event.tuplet_count == 6 for event in events)
    assert [group_ids.count(group_ids[index]) for index in range(0, 24, 6)] == [
        6,
        6,
        6,
        6,
    ]
    assert document.text.count("$") == 8
    assert svg.count('class="tuplet-bracket"') == 4
    assert {f"s1:i{100 + index}" for index in range(24)} <= {
        anchor.source_id for anchor in document.anchors
    }


def test_musicxml_provenance_produces_exact_utf16_anchors() -> None:
    xml = """
    <score-partwise version="4.0">
      <work><work-title>谱🎵</work-title></work>
      <part-list><score-part id="P1"><part-name>Music</part-name></score-part></part-list>
      <part id="P1"><measure number="1">
        <attributes>
          <divisions>1</divisions>
          <key><fifths>0</fifths></key>
          <time><beats>4</beats><beat-type>4</beat-type></time>
        </attributes>
        <note id="st__n-s1-i10__a-s1-i11__ss-s1-i12__ar-s1-i13">
          <pitch><step>C</step><alter>1</alter><octave>4</octave></pitch>
          <duration>1</duration>
          <accidental>sharp</accidental>
          <notations>
            <slur type="start"/>
            <articulations><staccato/></articulations>
          </notations>
        </note>
      </measure></part>
    </score-partwise>
    """

    document = score_to_jianpu_document(musicxml_to_score(xml))
    selected = {
        anchor.source_id: _utf16_slice(
            document.text, anchor.start_utf16, anchor.end_utf16
        )
        for anchor in document.anchors
    }

    assert selected == {
        "s1:i10": "1",
        "s1:i11": "#",
        "s1:i12": "(",
        "s1:i13": "^.",
    }
    assert len(document.text_hash) == 64


def test_augmentation_dot_provenance_produces_clickable_text_anchor() -> None:
    xml = """
    <score-partwise version="4.0">
      <part-list><score-part id="P1"><part-name>Music</part-name></score-part></part-list>
      <part id="P1"><measure number="1">
        <attributes>
          <divisions>1</divisions><key><fifths>0</fifths></key>
          <time><beats>4</beats><beat-type>4</beat-type></time>
        </attributes>
        <note id="st__n-s1-i10__ad-s1-i11">
          <pitch><step>C</step><octave>4</octave></pitch>
          <duration>3</duration><type>half</type><dot/>
        </note>
      </measure></part>
    </score-partwise>
    """

    score = musicxml_to_score(xml)
    event = score.measures[0].events[0]
    document = score_to_jianpu_document(score)

    assert event.source_roles["augmentation_dot"] == ["s1:i11"]
    dot_anchor = next(
        anchor for anchor in document.anchors if anchor.role == "augmentation_dot"
    )
    assert _utf16_slice(document.text, dot_anchor.start_utf16, dot_anchor.end_utf16) == "."


def test_current_text_anchors_are_embedded_in_render_group() -> None:
    text = "title=春\n1=C\n4/4\n1 2 3 4 |"
    start = text.index("2")
    anchor = TextAnchor(
        source_id="s1:i22",
        start_utf16=start,
        end_utf16=start + 1,
        role="note",
    )
    score = parse_jianpu_score(text)

    apply_text_anchors(score, [anchor])
    rendered = render_score_svg(score)

    assert "source-anchor" in rendered
    assert 'data-source-id="s1:i22"' in rendered


def test_native_overlay_contract_is_validated(tmp_path: Path) -> None:
    overlay = tmp_path / "overlay_sheet1.png"
    overlay.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + b"\x00\x00\x00\rIHDR"
        + struct.pack(">II", 100, 200)
        + b"\x08\x06\x00\x00\x00"
    )
    source_map = tmp_path / "score-link-map.json"
    source_map.write_text(
        json.dumps(
            {
                "version": 1,
                "sheets": [
                    {
                        "sheet_index": 1,
                        "width": 100,
                        "height": 200,
                        "overlay_file": overlay.name,
                        "elements": [],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    assert OverlayService().find_native_overlay(tmp_path) == (overlay, source_map)

    source_map.write_text('{"version":2}', encoding="utf-8")
    assert OverlayService().find_native_overlay(tmp_path) == (None, None)


def test_render_map_contains_selector_and_bbox(tmp_path: Path) -> None:
    score = parse_jianpu_score("1=C\n4/4\n1 |")
    score.measures[0].events[0].source_ids = ["s1:i10"]
    renderer = PublicationRenderer()
    pages = renderer.render_scores([score])
    paths = renderer.write_pages(pages, tmp_path / "page.svg")
    render_map_path = paths[0].with_suffix(".render-map.json")
    payload = json.loads(render_map_path.read_text(encoding="utf-8"))
    assert payload["version"] == 1
    assert payload["page_index"] == 0
    assert payload["anchors"][0]["source_id"] == "s1:i10"
    assert payload["anchors"][0]["selector"] == 'g[data-source-ids~="s1:i10"]'
    assert payload["anchors"][0]["bbox"]["width"] > 0


def test_batch_render_prefixes_colliding_source_ids() -> None:
    score = parse_jianpu_score("1=C\n4/4\n1 |")
    event = score.measures[0].events[0]
    event.source_ids = ["s1:i10"]
    event.source_roles = {"note": ["s1:i10"]}

    _tag_score_source_page(score, 3)

    assert event.source_ids == ["p3|s1:i10"]
    assert event.source_roles == {"note": ["p3|s1:i10"]}


def test_history_persists_current_provenance_snapshot(tmp_path: Path) -> None:
    anchor = TextAnchor(
        source_id="s1:i10",
        start_utf16=4,
        end_utf16=5,
        role="note",
    )
    service = HistoryService(tmp_path / "history.db")

    batch = service.create_batch(
        [
            HistoryPage(
                overlay_file_id="overlay-id",
                source_map_file_id="map-id",
                text_hash="abc",
                text_anchors=[anchor],
            )
        ]
    )
    restored = service.get_batch(batch.id)

    assert restored is not None
    assert restored.pages[0].overlay_file_id == "overlay-id"
    assert restored.pages[0].source_map_file_id == "map-id"
    assert restored.pages[0].text_hash == "abc"
    assert restored.pages[0].text_anchors == [anchor]


def _utf16_slice(text: str, start: int, end: int) -> str:
    encoded = text.encode("utf-16-le")
    return encoded[start * 2 : end * 2].decode("utf-16-le")


def _make_note_event(
    degree: int,
    source_id: str,
    *,
    dynamic: str | None = None,
    dynamic_source_id: str | None = None,
) -> Event:
    roles: dict[str, list[str]] = {}
    if dynamic and dynamic_source_id:
        roles["dynamic"] = [dynamic_source_id]
    return Event(
        kind="note",
        duration=Fraction(1, 1),
        pitches=[JianpuPitch(degree=degree, source_id=source_id)],
        dynamic=dynamic,
        source_roles=roles,
    )


def _make_measure(
    events: list[Event],
    *,
    target_key: str = "C",
    beats_per_measure: int = 4,
    beat_type: int = 4,
    repeat_start: bool = False,
) -> Measure:
    return Measure(
        source_number="1",
        events=events,
        target_key=target_key,
        beats_per_measure=beats_per_measure,
        beat_type=beat_type,
        repeat_start=repeat_start,
    )


def test_baseline_no_lead_tokens_degree_one_anchor() -> None:
    m1 = _make_measure([_make_note_event(1, "n1")], target_key="C")
    score = JianpuScore(measures=[m1])
    document = score_to_jianpu_document(score)

    n1 = next(a for a in document.anchors if a.source_id == "n1")
    assert _utf16_slice(document.text, n1.start_utf16, n1.end_utf16) == "1"
    assert n1.start_utf16 == len("1=C\n4/4\n")


def test_key_change_anchor_skips_lead_token() -> None:
    m1 = _make_measure([_make_note_event(1, "n1")], target_key="C")
    m2 = _make_measure([_make_note_event(1, "n2")], target_key="F")
    score = JianpuScore(measures=[m1, m2])
    document = score_to_jianpu_document(score)

    n2 = next(a for a in document.anchors if a.source_id == "n2")
    assert _utf16_slice(document.text, n2.start_utf16, n2.end_utf16) == "1"
    assert document.text[n2.start_utf16 - 1] == " "


def test_time_signature_change_anchor_skips_lead_token() -> None:
    m1 = _make_measure([_make_note_event(3, "n1")], target_key="C")
    m2 = _make_measure(
        [_make_note_event(3, "n2")],
        target_key="C",
        beats_per_measure=3,
        beat_type=4,
    )
    score = JianpuScore(measures=[m1, m2])
    document = score_to_jianpu_document(score)

    n2 = next(a for a in document.anchors if a.source_id == "n2")
    assert _utf16_slice(document.text, n2.start_utf16, n2.end_utf16) == "3"
    assert document.text[n2.start_utf16 - 1] == " "


def test_multiple_lead_tokens_and_repeat_prefix_anchor() -> None:
    m1 = _make_measure([_make_note_event(1, "n1")], target_key="C")
    m2 = _make_measure(
        [_make_note_event(1, "n2")],
        target_key="F",
        beats_per_measure=3,
        beat_type=4,
        repeat_start=True,
    )
    score = JianpuScore(measures=[m1, m2])
    document = score_to_jianpu_document(score)

    n2 = next(a for a in document.anchors if a.source_id == "n2")
    assert _utf16_slice(document.text, n2.start_utf16, n2.end_utf16) == "1"
    assert document.text[n2.start_utf16 - 1] == " "


def test_dynamic_anchor_after_lead_token() -> None:
    m1 = _make_measure([_make_note_event(1, "n1")], target_key="C")
    m2 = _make_measure(
        [_make_note_event(1, "n2", dynamic="f", dynamic_source_id="d2")],
        target_key="F",
    )
    score = JianpuScore(measures=[m1, m2])
    document = score_to_jianpu_document(score)

    n2 = next(a for a in document.anchors if a.source_id == "n2")
    d2 = next(a for a in document.anchors if a.source_id == "d2")
    assert _utf16_slice(document.text, n2.start_utf16, n2.end_utf16) == "1"
    assert _utf16_slice(document.text, d2.start_utf16, d2.end_utf16) == "\\f"
    assert document.text[n2.start_utf16 - 1] == " "


def test_missing_anchor_token_advances_to_next_logical_event() -> None:
    score = JianpuScore(
        measures=[
            _make_measure(
                [
                    _make_note_event(1, "missing", dynamic="f"),
                    _make_note_event(2, "n2"),
                ]
            )
        ]
    )
    text = "1=C\n4/4\n\\f 2 2 |"

    anchors = jianpu_writer._text_anchors_raw(
        score,
        text,
        accidental_mode="auto",
    )

    assert all(anchor.source_id != "missing" for anchor in anchors)
    n2 = next(anchor for anchor in anchors if anchor.source_id == "n2")
    assert text[n2.start_utf16 : n2.end_utf16] == "2"
    assert n2.start_utf16 == text.rfind("2")


def test_tuplet_without_id_is_bounded_by_declared_count() -> None:
    events = [
        Event(
            kind="note",
            duration=Fraction(1, 3) if index < 3 else Fraction(1, 1),
            pitches=[JianpuPitch(degree=degree)],
            tuplet_start=index == 0,
            tuplet_count=3 if index == 0 else None,
        )
        for index, degree in enumerate((1, 2, 3, 4))
    ]
    score = JianpuScore(measures=[_make_measure(events)])

    document = score_to_jianpu_document(score)

    assert "$123$ 4 |" in document.text
    assert "$1234$" not in document.text


def test_accidental_span_supports_postfix_double_accidentals() -> None:
    assert jianpu_writer._accidental_span("1bb") == (1, 3)
    assert jianpu_writer._accidental_span("2x") == (1, 2)


def test_tie_provenance_produces_clickable_tie_anchors() -> None:
    xml = """
    <score-partwise version="4.0">
      <part-list><score-part id="P1"><part-name>Music</part-name></score-part></part-list>
      <part id="P1">
        <measure number="1">
          <attributes>
            <divisions>1</divisions>
            <key><fifths>0</fifths></key>
            <time><beats>4</beats><beat-type>4</beat-type></time>
          </attributes>
          <note id="st__n-s1-i10__ss-s1-i12">
            <pitch><step>C</step><octave>4</octave></pitch>
            <duration>4</duration>
            <type>whole</type>
            <tie type="start"/>
          </note>
        </measure>
        <measure number="2">
          <note id="st__n-s1-i11__se-s1-i12">
            <pitch><step>C</step><octave>4</octave></pitch>
            <duration>4</duration>
            <type>whole</type>
            <tie type="stop"/>
          </note>
        </measure>
      </part>
    </score-partwise>
    """

    document = score_to_jianpu_document(musicxml_to_score(xml))
    tie_anchors = [a for a in document.anchors if a.role == "tie"]

    assert len(tie_anchors) >= 1
    assert all(a.source_id == "s1:i12" for a in tie_anchors)
    for anchor in tie_anchors:
        assert _utf16_slice(document.text, anchor.start_utf16, anchor.end_utf16) == "~"


def test_tie_and_slur_provenance_use_independent_source_roles() -> None:
    xml = """
    <score-partwise version="4.0">
      <part-list><score-part id="P1"><part-name>Music</part-name></score-part></part-list>
      <part id="P1"><measure number="1">
        <attributes>
          <divisions>1</divisions><key><fifths>0</fifths></key>
          <time><beats>4</beats><beat-type>4</beat-type></time>
        </attributes>
        <note id="st__n-s1-i10__ss-s1-i12__ts-s1-i14">
          <pitch><step>C</step><octave>4</octave></pitch>
          <duration>2</duration><type>half</type><tie type="start"/>
          <notations><slur type="start"/></notations>
        </note>
        <note id="st__n-s1-i11__se-s1-i12__te-s1-i14">
          <pitch><step>D</step><octave>4</octave></pitch>
          <duration>2</duration><type>half</type><tie type="stop"/>
          <notations><slur type="stop"/></notations>
        </note>
      </measure></part>
    </score-partwise>
    """

    document = score_to_jianpu_document(musicxml_to_score(xml))
    tie_anchors = [anchor for anchor in document.anchors if anchor.role == "tie"]
    slur_anchors = [anchor for anchor in document.anchors if anchor.role == "slur"]

    assert tie_anchors
    assert slur_anchors
    assert {anchor.source_id for anchor in tie_anchors} == {"s1:i14"}
    assert {anchor.source_id for anchor in slur_anchors} == {"s1:i12"}


def test_slur_provenance_still_produces_slur_anchors() -> None:
    xml = """
    <score-partwise version="4.0">
      <part-list><score-part id="P1"><part-name>Music</part-name></score-part></part-list>
      <part id="P1"><measure number="1">
        <attributes>
          <divisions>1</divisions>
          <key><fifths>0</fifths></key>
          <time><beats>4</beats><beat-type>4</beat-type></time>
        </attributes>
        <note id="st__n-s1-i10__ss-s1-i12">
          <pitch><step>C</step><octave>4</octave></pitch>
          <duration>2</duration>
          <type>half</type>
          <notations><slur type="start"/></notations>
        </note>
        <note id="st__n-s1-i11__se-s1-i12">
          <pitch><step>D</step><octave>4</octave></pitch>
          <duration>2</duration>
          <type>half</type>
          <notations><slur type="stop"/></notations>
        </note>
      </measure></part>
    </score-partwise>
    """

    document = score_to_jianpu_document(musicxml_to_score(xml))
    slur_anchors = [a for a in document.anchors if a.role == "slur"]

    assert len(slur_anchors) >= 1
    assert all(a.source_id == "s1:i12" for a in slur_anchors)
    for anchor in slur_anchors:
        char = _utf16_slice(document.text, anchor.start_utf16, anchor.end_utf16)
        assert char in {"(", ")"}
