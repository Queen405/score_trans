from score_trans.api.app import create_app


def test_render_routes_are_registered() -> None:
    paths = set(create_app().openapi()["paths"])

    assert "/render/final-output" in paths
    assert "/render/preserving-layout" in paths
