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
