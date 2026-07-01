from __future__ import annotations

import json
from pathlib import Path
import struct

from score_trans.domain.parse.jianpu_text import parse_jianpu_score
from score_trans.domain.parse.musicxml import musicxml_to_score
from score_trans.domain.provenance import apply_text_anchors
from score_trans.domain.write.jianpu_text import score_to_jianpu_document
from score_trans.exec.render.actions import _tag_score_source_page
from score_trans.models.history.entities import HistoryPage
from score_trans.models.provenance.schemas import TextAnchor
from score_trans.services.overlay.overlay_service import OverlayService
from score_trans.services.history.history_service import HistoryService
from score_trans.services.render.drawing.beat import _render_item
from score_trans.services.render.items.factory import _event_to_item
from score_trans.services.render.render_map import write_render_map


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
        "s1:i10": "2",
        "s1:i11": "#",
        "s1:i12": "(",
        "s1:i13": "^.",
    }
    assert len(document.text_hash) == 64


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
    event = score.measures[0].events[1]
    rendered = "\n".join(_render_item(_event_to_item(event), 100, 100, 40))

    assert 'class="source-anchor"' in rendered
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
    svg_path = tmp_path / "page.svg"
    svg_path.write_text(
        """
        <svg xmlns="http://www.w3.org/2000/svg">
          <g class="source-anchor" data-source-ids="s1:i10"
             data-bbox="12 34 56 78"><text>1</text></g>
        </svg>
        """,
        encoding="utf-8",
    )

    render_map_path = write_render_map(svg_path, 2)

    assert render_map_path is not None
    payload = json.loads(render_map_path.read_text(encoding="utf-8"))
    assert payload["anchors"] == [
        {
            "source_id": "s1:i10",
            "page_index": 2,
            "selector": 'g[data-source-ids~="s1:i10"]',
            "bbox": {"x": 12.0, "y": 34.0, "width": 56.0, "height": 78.0},
        }
    ]


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
