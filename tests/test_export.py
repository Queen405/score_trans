from __future__ import annotations

import xml.etree.ElementTree as ET

import fitz
import mido
import pytest
from score_trans.domain.jianpu import (
    jianpu_to_musicxml,
    parse_jianpu_score,
)
from score_trans.exec.export.actions import ExportActions
from score_trans.models.export.schemas import (
    ExportMidiTextRequest,
    ExportMusicXmlRequest,
    ExportMusicXmlTextRequest,
    ExportRenderedImagesRequest,
    ExportRenderedPdfRequest,
    ExportResponse,
)
from score_trans.services.export.export_service import (
    ExportService,
    svg_page_to_image,
    svg_pages_to_pdf,
)
from score_trans.services.files.upload_service import UploadService
from score_trans.services.render.engraving.scene import PublicationScene, SceneNode
from score_trans.services.render.engraving.style import PublicationStyle
from score_trans.services.render.engraving.svg_backend import scene_to_svg
from score_trans.services.render.main import render_scores_a4_pages


def test_export_service_writes_musicxml(tmp_path) -> None:
    xml_text = jianpu_to_musicxml("1=C\n4/4\n1 2 3 4 |")
    output_path = tmp_path / "out.musicxml"

    from score_trans.domain.musicxml import musicxml_to_score

    score = musicxml_to_score(xml_text)
    ExportService().export_musicxml(score, output_path, title="Test Score")

    assert output_path.exists()
    written = output_path.read_text(encoding="utf-8")
    assert '<?xml version="1.0"' in written
    assert "<score-partwise" in written
    assert "<work-title>Test Score</work-title>" in written


def test_export_musicxml_text_from_jianpu() -> None:
    actions = ExportActions(uploads=UploadService())
    req = ExportMusicXmlTextRequest(
        jianpu_text="title=测试\n1=G\n3/4\n1 2 3 |",
        filename="test.musicxml",
    )

    resp = actions.export_musicxml_text(req)

    assert isinstance(resp, ExportResponse)
    assert resp.filename == "test.musicxml"
    path = actions.uploads.get_path(resp.file_id)
    assert path is not None and path.exists()
    written = path.read_text(encoding="utf-8")
    assert "<work-title>测试</work-title>" in written
    assert "<fifths>1</fifths>" in written


def test_export_musicxml_from_file_id(tmp_path) -> None:
    uploads = UploadService()
    original = tmp_path / "original.musicxml"
    original.write_text(jianpu_to_musicxml("1=C\n4/4\n1 2 3 4 |"), encoding="utf-8")
    file_id = uploads.register(original)

    actions = ExportActions(uploads=uploads)
    req = ExportMusicXmlRequest(
        musicxml_file_id=file_id,
        target_key="D",
        filename="transposed.musicxml",
    )

    resp = actions.export_musicxml(req)

    assert resp.filename == "transposed.musicxml"
    path = uploads.get_path(resp.file_id)
    assert path is not None and path.exists()
    written = path.read_text(encoding="utf-8")
    assert "<fifths>2</fifths>" in written


def _register_svg_page(uploads: UploadService, tmp_path, name: str, x: int) -> str:
    path = tmp_path / name
    path.write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="595" height="842" '
        f'viewBox="0 0 595 842"><path d="M{x} 20h100v20h-100z"/></svg>',
        encoding="utf-8",
    )
    return uploads.register(path)


def test_rendered_pdf_export_uses_svg_pages_directly(tmp_path) -> None:
    uploads = UploadService()
    page_ids = [
        _register_svg_page(uploads, tmp_path, "page-1.svg", 20),
        _register_svg_page(uploads, tmp_path, "page-2.svg", 40),
    ]

    response = ExportActions(uploads=uploads).export_rendered_pdf(
        ExportRenderedPdfRequest(svg_file_ids=page_ids, filename="score")
    )

    output = uploads.get_path(response.file_id)
    assert output is not None and output.read_bytes().startswith(b"%PDF")
    assert response.filename == "score.pdf"
    assert len(fitz.open(output)) == 2


@pytest.mark.parametrize(
    ("image_format", "magic", "suffix"),
    [("png", b"\x89PNG", ".png"), ("jpeg", b"\xff\xd8\xff", ".jpg")],
)
def test_rendered_image_export_uses_svg_page_directly(
    tmp_path, image_format: str, magic: bytes, suffix: str
) -> None:
    uploads = UploadService()
    page_id = _register_svg_page(uploads, tmp_path, "page.svg", 20)

    response = ExportActions(uploads=uploads).export_rendered_images(
        ExportRenderedImagesRequest(
            svg_file_ids=[page_id],
            filename="score",
            format=image_format,
            dpi=150,
        )
    )

    output = uploads.get_path(response.files[0].file_id)
    assert output is not None and output.read_bytes().startswith(magic)
    assert response.files[0].filename == f"score{suffix}"


def test_text_exports_preserve_multi_part_structure() -> None:
    uploads = UploadService()
    actions = ExportActions(uploads=uploads)
    text = (
        '// @part 1 name="高音"\n1=C\n4/4\n1 2 3 4 |\n'
        '// @part 2 name="低音"\n1=C\n4/4\n5 6 7 1\' |'
    )

    xml_response = actions.export_musicxml_text(
        ExportMusicXmlTextRequest(jianpu_text=text, title="双声部")
    )
    xml_path = uploads.get_path(xml_response.file_id)
    assert xml_path is not None
    root = ET.fromstring(xml_path.read_text(encoding="utf-8"))
    assert len(root.findall("./part-list/score-part")) == 2
    assert len(root.findall("./part")) == 2

    midi_response = actions.export_midi_text(
        ExportMidiTextRequest(jianpu_text=text, title="双声部")
    )
    midi_path = uploads.get_path(midi_response.file_id)
    assert midi_path is not None
    midi = mido.MidiFile(midi_path)
    assert len(midi.tracks) == 2


def test_multi_page_midi_merges_parts_across_pages(tmp_path) -> None:
    uploads = UploadService()
    actions = ExportActions(uploads=uploads)
    text = (
        '// @page 1 name="p1.png"\n'
        '// @part 1 name="Voice"\n1=C\n4/4\n1 2 3 4 |\n'
        '// @part 2 name="Piano"\n1=C\n4/4\n5 6 7 1\' |\n'
        '// @page 2 name="p2.png"\n'
        '// @part 1 name="Voice"\n1=C\n4/4\n2 3 4 5 |\n'
        "// @part 2 name=\"Piano\"\n1=C\n4/4\n6 7 1' 2' |"
    )

    midi_response = actions.export_midi_text(
        ExportMidiTextRequest(jianpu_text=text, title="多页多声部")
    )
    midi_path = uploads.get_path(midi_response.file_id)
    assert midi_path is not None
    midi = mido.MidiFile(midi_path)
    assert len(midi.tracks) == 2

    for track in midi.tracks:
        abs_time = 0
        note_times: list[int] = []
        for msg in track:
            abs_time += msg.time
            if msg.type == "note_on" and msg.velocity > 0:
                note_times.append(abs_time)
        assert len(note_times) == 8, (
            f"Track {track.name}: expected 8 notes, got {len(note_times)}"
        )
        assert note_times[3] < note_times[4], (
            f"Track {track.name}: page 2 notes must start after page 1 ends, "
            f"got {note_times[3]} -> {note_times[4]}"
        )


def test_midi_export_rejects_microtones_without_pitch_bend(tmp_path) -> None:
    score = parse_jianpu_score("1=C\n4/4\nqs1 2 3 4 |")
    output_path = tmp_path / "microtonal.mid"

    with pytest.raises(ValueError, match="pitch bend"):
        ExportService().export_midi(score, output_path)

    assert not output_path.exists()


def _midi_tempo_events(midi: mido.MidiFile) -> list[tuple[int, float]]:
    absolute_tick = 0
    events: list[tuple[int, float]] = []
    for msg in midi.tracks[0]:
        absolute_tick += msg.time
        if msg.type == "set_tempo":
            events.append((absolute_tick, mido.tempo2bpm(msg.tempo)))
    return events


def test_midi_export_uses_score_tempo(tmp_path) -> None:
    score = parse_jianpu_score("1=C\ntempo=60\n4/4\n1 2 3 4 |")
    output_path = tmp_path / "with_tempo.mid"
    ExportService().export_midi_scores([score], output_path)

    midi = mido.MidiFile(output_path)
    assert _midi_tempo_events(midi) == [(0, pytest.approx(60))]


def test_midi_export_tempo_falls_back_to_default(tmp_path) -> None:
    from score_trans.models.score import DEFAULT_TEMPO

    score = parse_jianpu_score("1=C\n4/4\n1 2 3 4 |")
    output_path = tmp_path / "no_tempo.mid"
    ExportService().export_midi_scores([score], output_path)

    midi = mido.MidiFile(output_path)
    assert _midi_tempo_events(midi) == [(0, pytest.approx(DEFAULT_TEMPO))]


def test_midi_export_writes_measure_level_tempo_map(tmp_path) -> None:
    score = parse_jianpu_score(
        "tempo=120\n1=C\n4/4\n1 2 3 4 |\ntempo=80\n5 6 7 1 |\n1 2 3 4 |"
    )
    output_path = tmp_path / "tempo-map.mid"
    ExportService().export_midi_scores([score], output_path)

    midi = mido.MidiFile(output_path)
    assert _midi_tempo_events(midi) == [
        (0, pytest.approx(120)),
        (4 * midi.ticks_per_beat, pytest.approx(80)),
    ]


def test_midi_export_tempo_only_on_track0(tmp_path) -> None:
    """set_tempo 仅写在 track 0，非首 track 不写（符合 MIDI 规范）。"""
    text = (
        '// @part 1 name="高音"\n1=C\n4/4\n1 2 3 4 |\n'
        '// @part 2 name="低音"\n1=C\n4/4\n5 6 7 1\' |'
    )
    actions = ExportActions(uploads=UploadService())
    resp = actions.export_midi_text(ExportMidiTextRequest(jianpu_text=text))
    midi_path = actions.uploads.get_path(resp.file_id)
    assert midi_path is not None
    midi = mido.MidiFile(midi_path)

    assert len(midi.tracks) == 2
    tempo_msgs = [
        msg for track in midi.tracks for msg in track if msg.type == "set_tempo"
    ]
    assert len(tempo_msgs) == 1, "set_tempo 应仅出现一次（track 0）"
    assert _midi_tempo_events(midi) == [(0, pytest.approx(120))]


def test_midi_export_writes_time_signature(tmp_path) -> None:
    """track 0 写入 time_signature meta，拍号从 score 读取。"""
    score_44 = parse_jianpu_score("1=C\n4/4\n1 2 3 4 |")
    output_44 = tmp_path / "ts_44.mid"
    ExportService().export_midi_scores([score_44], output_44)
    midi_44 = mido.MidiFile(output_44)
    ts_msgs = [m for m in midi_44.tracks[0] if m.type == "time_signature"]
    assert len(ts_msgs) == 1
    assert ts_msgs[0].numerator == 4
    assert ts_msgs[0].denominator == 4

    # 3/8 拍号
    score_38 = parse_jianpu_score("1=C\n3/8\n1 2 3 |")
    output_38 = tmp_path / "ts_38.mid"
    ExportService().export_midi_scores([score_38], output_38)
    midi_38 = mido.MidiFile(output_38)
    ts_38 = [m for m in midi_38.tracks[0] if m.type == "time_signature"]
    assert len(ts_38) == 1
    assert ts_38[0].numerator == 3
    assert ts_38[0].denominator == 8


def test_export_midi_route_uses_source_tempo_and_has_no_override(tmp_path) -> None:
    from score_trans.models.export.schemas import ExportMidiRequest

    uploads = UploadService()
    original = tmp_path / "original.musicxml"
    original.write_text(
        jianpu_to_musicxml("tempo=100\n1=C\n4/4\n1 2 3 4 |"),
        encoding="utf-8",
    )
    file_id = uploads.register(original)

    actions = ExportActions(uploads=uploads)
    req = ExportMidiRequest(
        musicxml_file_id=file_id,
        target_key="G",
        filename="test.mid",
    )
    resp = actions.export_midi(req)

    assert resp.filename == "test.mid"
    midi_path = uploads.get_path(resp.file_id)
    assert midi_path is not None and midi_path.exists()
    midi = mido.MidiFile(midi_path)
    assert _midi_tempo_events(midi) == [(0, pytest.approx(100))]
    assert "midi_tempo" not in ExportMidiRequest.model_fields
    assert "midi_tempo" not in ExportMidiTextRequest.model_fields


def _a4_svg_from_jianpu(text: str) -> str:
    return render_scores_a4_pages([parse_jianpu_score(text)])[0].svg


def _pixel_ratios(pixmap: fitz.Pixmap) -> tuple[float, float]:
    """返回 (纯黑像素占比, 纯白像素占比)。"""
    total = pixmap.width * pixmap.height
    black = pixmap.samples.count(b"\x00\x00\x00") / total
    white = pixmap.samples.count(b"\xff\xff\xff") / total
    return black, white


def test_rendered_png_export_is_not_monochrome(tmp_path) -> None:
    """回归：MuPDF 不解析 <style>，修复前导出 PNG 约 99.9% 纯黑。"""
    svg = _a4_svg_from_jianpu("1=C\n4/4\n1 2 3 4 | 5 6 7 1' |")
    output = tmp_path / "page.png"

    svg_page_to_image(svg.encode("utf-8"), output, dpi=72)

    assert output.read_bytes().startswith(b"\x89PNG")
    document = fitz.open(output)
    try:
        pixmap = document[0].get_pixmap()
    finally:
        document.close()
    black, white = _pixel_ratios(pixmap)

    assert black < 0.99, f"导出 PNG 仍接近全黑（black={black:.2%}），CSS 未内联"
    ink = 1.0 - white
    assert ink > 0.001, f"导出 PNG 墨迹不足（ink={ink:.2%}），内容未渲染"


def test_rendered_pdf_export_is_not_monochrome_and_hides_helper_text(tmp_path) -> None:
    """回归：PDF 导出同样全黑；且 opacity=0 辅助文本被画进文本层。"""
    svg = _a4_svg_from_jianpu("1=C\n4/4\n1 2 3 4 | 5 6 7 1' |")
    output = tmp_path / "score.pdf"

    svg_pages_to_pdf([svg.encode("utf-8")], output)

    assert output.read_bytes().startswith(b"%PDF")
    document = fitz.open(output)
    try:
        assert len(document) == 1
        pixmap = document[0].get_pixmap()
        black, white = _pixel_ratios(pixmap)
        text_layer = str(document[0].get_text())
    finally:
        document.close()

    assert black < 0.99, f"导出 PDF 仍接近全黑（black={black:.2%}），CSS 未内联"
    ink = 1.0 - white
    assert ink > 0.0005, f"导出 PDF 墨迹不足（ink={ink:.2%}），内容未渲染"
    assert not text_layer.strip(), (
        f"opacity=0 辅助文本泄漏进 PDF 文本层: {text_layer!r}"
    )


def test_scene_to_svg_inlines_class_presentation_attributes() -> None:
    scene = PublicationScene(100.0, 100.0, 0)
    scene.add(
        SceneNode(
            "rect",
            {
                "class": "page-background",
                "x": 0,
                "y": 0,
                "width": 100,
                "height": 100,
            },
        )
    )
    scene.add(
        SceneNode(
            "line",
            {
                "class": "measure",
                "x1": 1,
                "y1": 2,
                "x2": 3,
                "y2": 4,
                "stroke-width": 2.5,
            },
        )
    )

    root = ET.fromstring(scene_to_svg(scene, PublicationStyle()))
    background = next(
        node for node in root.iter() if node.attrib.get("class") == "page-background"
    )
    measure = next(
        node for node in root.iter() if node.attrib.get("class") == "measure"
    )

    assert background.attrib["fill"] == "#fff"
    assert measure.attrib["stroke"] == "#171717"
    assert measure.attrib["fill"] == "none"
    assert measure.attrib["stroke-linecap"] == "round"
    assert measure.attrib["stroke-width"] == "2.5"  # 内联属性优先，不被 CSS 覆盖


def test_scene_to_svg_keeps_existing_inline_fill_over_css() -> None:
    scene = PublicationScene(100.0, 100.0, 0)
    scene.add(
        SceneNode(
            "circle",
            {"class": "rhythm-dot", "cx": 1, "cy": 2, "r": 1.5, "fill": "#ff0000"},
        )
    )

    svg = scene_to_svg(scene, PublicationStyle())
    root = ET.fromstring(svg)
    dot = next(node for node in root.iter() if node.attrib.get("class") == "rhythm-dot")

    assert dot.attrib["fill"] == "#ff0000"
    assert svg.count('fill="#171717"') == 0


def test_rendered_svg_elements_carry_paint_attributes() -> None:
    """真实渲染产物：带 class 的元素序列化后带 fill/stroke，文本组继承填充色。"""
    root = ET.fromstring(_a4_svg_from_jianpu("1=C\n4/4\n1 2 3 4 |"))

    background = next(
        node for node in root.iter() if node.attrib.get("class") == "page-background"
    )
    assert background.attrib["fill"] == "#fff"

    barlines = [
        node
        for node in root.iter()
        if "measure" in node.attrib.get("class", "").split()
    ]
    assert barlines
    for node in barlines:
        assert node.attrib["stroke"] == "#171717"
        assert node.attrib["fill"] == "none"

    title = next(
        node for node in root.iter() if node.attrib.get("class") == "score-meta"
    )
    assert title.attrib["fill"] == "#181818"

    # 渲染器原本就内联 fill="#171717" 的元素（如 octave-dot）属性必须保留
    score_with_dot = _a4_svg_from_jianpu("1=C\n4/4\n1 2 3 1' |")
    dotted_root = ET.fromstring(score_with_dot)
    dots = [
        node for node in dotted_root.iter() if node.attrib.get("class") == "octave-dot"
    ]
    assert dots
    assert all(node.attrib["fill"] == "#171717" for node in dots)
