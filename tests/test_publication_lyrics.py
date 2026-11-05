from __future__ import annotations

from fractions import Fraction
import xml.etree.ElementTree as ET

import pytest
from score_trans.models.score import Event, JianpuPitch, Measure, TextBlock
from score_trans.services.render.engraving.fonts import font_registry
from score_trans.services.render.engraving.renderer import (
    _Anchor,
    _measure_text_layout,
    _spanner,
)
from score_trans.services.render.engraving.scene import BBox, PublicationScene
from score_trans.services.render.engraving.style import PublicationStyle
from score_trans.services.render.engraving.svg_backend import scene_to_svg


def _measure(lyric: str = "") -> Measure:
    return Measure(
        "1",
        duration=Fraction(4),
        events=[
            Event(
                "note",
                Fraction(1),
                [JianpuPitch(index + 1)],
                start=Fraction(index),
                lyric=lyric if index == 0 else None,
            )
            for index in range(4)
        ],
    )


def test_east_asian_lyrics_are_centered_and_punctuation_hangs() -> None:
    style = PublicationStyle()
    plain = _measure("春")
    punctuated = _measure("春，")
    spans = [
        (event.start, event.start + event.duration, 100 + index * 80)
        for index, event in enumerate(plain.events)
    ]
    plain_layout = _measure_text_layout(plain, 0, 500, 0, style, event_spans=spans)[0]
    punctuated_layout = _measure_text_layout(
        punctuated, 0, 500, 0, style, event_spans=spans
    )[0]
    assert plain_layout.bbox.x + plain_layout.bbox.width / 2 == pytest.approx(100)
    # The comma hangs right; it is not counted as part of the centered Han character.
    assert punctuated_layout.bbox.x + punctuated_layout.bbox.width / 2 > 100


def test_melisma_remains_left_aligned_to_its_starting_note() -> None:
    measure = _measure()
    measure.text_blocks = [
        TextBlock("春", role="lyric", start=Fraction(0), duration=Fraction(1)),
        TextBlock("晓", role="lyric", start=Fraction(2), duration=Fraction(1)),
    ]
    spans = [
        (event.start, event.start + event.duration, 100 + index * 80)
        for index, event in enumerate(measure.events)
    ]
    layout = _measure_text_layout(
        measure, 0, 500, 0, PublicationStyle(), event_spans=spans
    )[0]
    ink_left = font_registry().ink_bounds("春", 18, 500)[0]
    assert layout.bbox.x - ink_left == pytest.approx(100)


def test_slurs_and_ties_use_tapered_filled_outlines() -> None:
    event = Event("note", Fraction(1), [JianpuPitch(1)], start=Fraction(0))
    start = _Anchor(100, 100, BBox(90, 80, 20, 30), event)
    end = _Anchor(240, 100, BBox(230, 80, 20, 30), event)
    for kind in ("slur", "tie"):
        scene = PublicationScene(400, 300, 0)
        scene.add(_spanner(kind, start, end))
        root = ET.fromstring(scene_to_svg(scene, PublicationStyle()))
        path = next(item for item in root.iter() if item.attrib.get("class") == kind)
        assert path.attrib["d"].endswith("Z")
        assert path.attrib["fill"] == "#171717"
        assert "stroke-width" not in path.attrib
