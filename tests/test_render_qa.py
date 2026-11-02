from __future__ import annotations

from score_trans.services.render.engraving.qa import check_scene_geometry
from score_trans.services.render.engraving.scene import (
    BBox,
    PublicationScene,
    SceneNode,
)
from score_trans.services.render.engraving.style import PublicationStyle


def _anchor(x: float, y: float, width: float, height: float) -> SceneNode:
    return SceneNode(
        "g",
        {
            "class": "source-anchor",
            "data-bbox": BBox(x, y, width, height).as_data(),
        },
    )


def test_geometry_qa_accepts_separate_in_bounds_events() -> None:
    scene = PublicationScene(400, 400, 0)
    scene.add(_anchor(100, 100, 30, 30))
    scene.add(_anchor(150, 100, 30, 30))

    assert (
        check_scene_geometry(scene, PublicationStyle(page_width=400, page_height=400))
        == []
    )


def test_geometry_qa_reports_event_overlap_and_page_overflow() -> None:
    scene = PublicationScene(400, 400, 0)
    scene.add(_anchor(100, 100, 50, 50))
    scene.add(_anchor(120, 120, 50, 50))
    scene.add(_anchor(380, 100, 40, 20))

    issues = check_scene_geometry(
        scene, PublicationStyle(page_width=400, page_height=400)
    )

    assert {issue["kind"] for issue in issues} == {"event-overlap", "page-overflow"}


def test_geometry_qa_checks_nested_text_and_path_geometry() -> None:
    scene = PublicationScene(400, 400, 0)
    scene.add(
        SceneNode(
            "g",
            {"class": "source-anchor", "data-bbox": BBox(100, 100, 30, 30).as_data()},
            children=[
                SceneNode(
                    "text",
                    {"class": "lyric", "data-bbox": BBox(390, 100, 80, 20).as_data()},
                    text="overflow",
                ),
                SceneNode(
                    "path",
                    {"class": "slur", "data-bbox": BBox(100, -10, 40, 8).as_data()},
                ),
            ],
        )
    )

    issues = check_scene_geometry(
        scene, PublicationStyle(page_width=400, page_height=400)
    )

    assert sum(issue["kind"] == "page-overflow" for issue in issues) == 2


def test_geometry_qa_does_not_record_mark_primitives_separately() -> None:
    scene = PublicationScene(400, 400, 0)
    scene.add(
        SceneNode(
            "g",
            {
                "class": "performance-mark technical",
                "data-source-ids": "mark-1",
                "data-bbox": BBox(100, 100, 30, 30).as_data(),
            },
            children=[
                SceneNode(
                    "path",
                    {
                        "class": "performance-mark-primitive performance-mark-stroke",
                        "data-bbox": BBox(105, 105, 20, 2).as_data(),
                    },
                )
            ],
        )
    )

    issues = check_scene_geometry(
        scene, PublicationStyle(page_width=400, page_height=400)
    )

    assert issues == []
    assert [record.kind for record in scene.geometry_records] == ["performance-mark"]


def test_geometry_qa_persists_diagnostics_on_scene() -> None:
    scene = PublicationScene(400, 400, 0)
    scene.add(_anchor(390, 100, 40, 20))

    issues = check_scene_geometry(
        scene, PublicationStyle(page_width=400, page_height=400)
    )

    assert scene.geometry_issues == issues
    assert scene.render_map_payload()["diagnostics"] == issues


def test_geometry_qa_uses_virtual_bounds_for_scaled_a4_scene() -> None:
    scene = PublicationScene(400, 400, 0, coordinate_scale=0.5)
    scene.add(_anchor(700, 100, 40, 20))

    issues = check_scene_geometry(
        scene, PublicationStyle(page_width=800, page_height=800)
    )

    assert not any(issue["kind"] == "page-overflow" for issue in issues)


def test_render_map_scales_diagnostic_bboxes_to_physical_coordinates() -> None:
    scene = PublicationScene(400, 400, 0, coordinate_scale=0.5)
    scene.geometry_issues = [
        {
            "kind": "page-overflow",
            "classes": ("note",),
            "bbox": (700.0, 100.0, 40.0, 20.0),
            "owner": "note-1",
        }
    ]

    diagnostic = scene.render_map_payload()["diagnostics"][0]

    assert diagnostic["bbox"] == (350.0, 50.0, 20.0, 10.0)


def test_geometry_qa_excludes_spanners_from_event_overlap() -> None:
    scene = PublicationScene(400, 400, 0)
    scene.add(
        SceneNode(
            "g",
            {
                "class": "source-anchor",
                "data-source-ids": "note-1",
                "data-bbox": BBox(100, 100, 40, 40).as_data(),
            },
        )
    )
    scene.add(
        SceneNode(
            "path",
            {
                "class": "slur",
                "data-geometry-owner": "span:slur",
                "data-bbox": BBox(120, 120, 80, 12).as_data(),
            },
        )
    )

    issues = check_scene_geometry(
        scene, PublicationStyle(page_width=400, page_height=400)
    )

    assert not any(issue["kind"] == "geometry-overlap" for issue in issues)


def test_measure_content_overflow_uses_actual_ink_instead_of_clipped_layout_box() -> (
    None
):
    scene = PublicationScene(400, 400, 0)
    scene.add(
        SceneNode(
            "g",
            {
                "class": "source-anchor",
                "data-bbox": BBox(190, 100, 40, 30).as_data(),
                "data-content-start": 100,
                "data-content-end": 200,
            },
        )
    )

    issues = check_scene_geometry(
        scene, PublicationStyle(page_width=400, page_height=400)
    )

    assert any(issue["kind"] == "measure-overflow" for issue in issues)
