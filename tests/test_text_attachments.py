from __future__ import annotations

from fractions import Fraction

from score_trans.domain.text_attachments import build_source_text_attachments
from score_trans.domain.text_placement import place_source_text_attachments
from score_trans.models.provenance.schemas import (
    BoundingBox,
    MusicXmlLocator,
    SourceTextAttachment,
    SourceElement,
    SourceMap,
    SourceMapSheet,
    TextPlacementAnchor,
)
from score_trans.models.render.schemas import RenderPageMeasureRange
from score_trans.models.score import Event, JianpuPitch, JianpuScore, Measure, TextBlock


def _score() -> JianpuScore:
    event = Event(
        kind="note",
        duration=Fraction(1, 1),
        pitches=[JianpuPitch(degree=1, source_id="s1:i10")],
        lyric="春",
        dynamic="mf",
        source_ids=["s1:i10"],
        source_roles={"note": ["s1:i10"]},
    )
    return JianpuScore(
        title="测试曲",
        measures=[
            Measure(
                source_number="1",
                display_measure_number=1,
                duration=Fraction(4, 1),
                events=[event],
            )
        ],
    )


def _source_map() -> SourceMap:
    return SourceMap(
        sheets=[
            SourceMapSheet(
                sheet_index=1,
                width=1000,
                height=1600,
                overlay_file="overlay.png",
                elements=[
                    SourceElement(
                        source_id="s1:i10",
                        inter_id=10,
                        shape="NOTEHEAD_BLACK",
                        grade=0.98,
                        bounds=BoundingBox(x=460, y=720, width=30, height=24),
                        hit_path="M460 720h30v24h-30Z",
                        musicxml_locator=MusicXmlLocator(contains="n-s1-i10"),
                    )
                ],
            )
        ]
    )


def test_build_source_text_attachments_deduplicates_semantic_text_and_anchors() -> None:
    blocks = [
        TextBlock("测试曲", bbox=(100, 20, 600, 80), role="title"),
        TextBlock("春", bbox=(450, 755, 490, 790), role="lyric"),
        TextBlock("mf", bbox=(450, 680, 500, 710), role="expression"),
        TextBlock("提示", bbox=(430, 650, 520, 690), role="other"),
        TextBlock("12", bbox=(40, 600, 70, 630), role="measure_number"),
        TextBlock("版权所有", bbox=(300, 1500, 700, 1540), role="footer"),
    ]

    attachments = build_source_text_attachments(blocks, _score(), _source_map())

    assert [item.text for item in attachments] == ["提示", "版权所有"]
    assert attachments[0].anchor.kind == "source_element"
    assert attachments[0].anchor.source_id == "s1:i10"
    assert attachments[0].anchor.relative_y == 0.41875
    assert attachments[1].anchor.kind == "score_end"


def test_build_source_text_attachments_uses_relative_y_without_source_map() -> None:
    blocks = [
        TextBlock(
            "第二段提示",
            bbox=(100, 900, 400, 950),
            role="other",
            confidence=0.8,
        )
    ]

    attachments = build_source_text_attachments(
        blocks,
        _score(),
        None,
        image_size=(1000, 1600),
    )

    assert len(attachments) == 1
    attachment = attachments[0]
    assert attachment.anchor.kind == "source_relative"
    assert attachment.anchor.relative_y == 0.578125
    assert attachment.ocr_confidence == 0.8


def test_place_source_text_attachments_uses_source_anchor_and_relative_fallback() -> (
    None
):
    attachments = [
        SourceTextAttachment(
            id="middle",
            text="中段提示",
            role="expression",
            anchor=TextPlacementAnchor(
                kind="source_element",
                source_id="s1:i50",
                relative_y=0.55,
                offset_x=12,
                offset_y=7,
            ),
        ),
        SourceTextAttachment(
            id="late",
            text="末段提示",
            role="other",
            anchor=TextPlacementAnchor(kind="source_relative", relative_y=0.95),
        ),
    ]
    layout_svgs = [
        '<svg xmlns="http://www.w3.org/2000/svg"/>',
        (
            '<svg xmlns="http://www.w3.org/2000/svg">'
            '<g data-source-ids="p0|s1:i50" data-bbox="500 700 24 30"/>'
            "</svg>"
        ),
        '<svg xmlns="http://www.w3.org/2000/svg"/>',
    ]
    ranges = [
        [
            RenderPageMeasureRange(
                source_page_index=0,
                start_measure_number=1,
                end_measure_number=40,
            )
        ],
        [
            RenderPageMeasureRange(
                source_page_index=0,
                start_measure_number=41,
                end_measure_number=80,
            )
        ],
        [
            RenderPageMeasureRange(
                source_page_index=0,
                start_measure_number=81,
                end_measure_number=90,
            )
        ],
    ]

    result = place_source_text_attachments([attachments], layout_svgs, ranges)

    assert [block.text for block in result.rendered_blocks_by_page[1]] == ["中段提示"]
    assert [block.text for block in result.rendered_blocks_by_page[2]] == ["末段提示"]
    middle = result.rendered_blocks_by_page[1][0]
    assert middle.bbox.x == 484
    assert middle.bbox.y == 663
