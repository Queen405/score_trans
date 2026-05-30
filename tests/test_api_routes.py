from score_trans.api.app import create_app


def test_render_routes_are_registered() -> None:
    paths = set(create_app().openapi()["paths"])

    assert "/render/final-output" in paths
    assert "/render/preserving-layout" in paths


def test_jianpu_svg_request_accepts_page_image_for_ocr_overlay() -> None:
    schema = create_app().openapi()["components"]["schemas"]["RenderJianpuSvgRequest"]

    assert "page_image_file_id" in schema["properties"]
