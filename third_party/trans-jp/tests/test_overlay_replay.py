from __future__ import annotations

from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree as ET
import hashlib
import json
from PIL import Image
import pytest

from trans_jp.io.replay_reader import ReplayClient
from trans_jp.io.output_writer import write_outputs
from trans_jp.models.contracts import CliConfig, LlmConfig
from trans_jp.pipeline.runner import run

FIXTURES = Path(__file__).parent / "fixtures/liangzhu"
SOURCE = Path(__file__).parents[1] / "examples/image.png"


@pytest.fixture(scope="module")
def replay(tmp_path_factory):
    output = tmp_path_factory.mktemp("replay")
    result = run(
        CliConfig(SOURCE, output, LlmConfig("", "", ""), debug=True),
        ReplayClient(FIXTURES),
    )
    write_outputs(result, output)
    return result, output


def test_real_page_frozen_reference(replay):
    result, output = replay
    manifest = json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == manifest["sha256"]
    elements = result.source_map["sheets"][0]["elements"]
    assert len(elements) == 60
    assert not result.warnings
    root = ET.fromstring(result.overlay_svg)
    ns = {"s": "http://www.w3.org/2000/svg"}
    assert len(root.findall("s:g", ns)) == 60
    assert not root.findall(".//s:text", ns)
    assert len(root.findall('.//s:path[@data-mark="slur"]', ns)) == 5
    # Real octaves must not get selected as tiny digit bodies.
    assert all(
        box.height > 8
        for row in result.rows
        for token in row.tokens
        for box in token.geometry.bodies
    )
    with (
        Image.open(BytesIO(result.preview_png)) as preview,
        Image.open(SOURCE) as original,
    ):
        assert preview.size == original.size == (721, 1020)
        assert (
            preview.crop((0, 0, 721, 150)).tobytes()
            == original.convert("RGB").crop((0, 0, 721, 150)).tobytes()
        )
    assert (output / "overlay-debug.svg").is_file()
    raw = json.loads((output / "rows/row_2.json").read_text(encoding="utf-8"))
    assert raw["tokens"][0]["x"] == result.rows[2].tokens[0].x
    assert "geometry" not in raw["tokens"][0]


def test_source_map_remains_compatible_with_desktop(replay):
    schemas = pytest.importorskip("score_trans.models.provenance.schemas")
    result, _ = replay
    source = schemas.SourceMap.model_validate(result.source_map)
    anchors = [schemas.TextAnchor.model_validate(a) for a in result.text_anchors]
    assert {e.source_id for e in source.sheets[0].elements} == {
        a.source_id for a in anchors if a.valid
    }
