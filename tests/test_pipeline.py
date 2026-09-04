import json
from pathlib import Path
from zipfile import ZipFile

import pytest
from PIL import Image
from score_trans.domain.jianpu import jianpu_to_musicxml
from score_trans.exec.pipeline.actions import (
    FullPipelineAction,
    PipelineActions,
    ScorePipelineOutputs,
    _find_omr_file,
    _generate_overlay,
    _unmapped_omr_warnings,
)
from score_trans.models.common.errors import RenderError
from score_trans.models.pipeline.schemas import PipelineResponse
from score_trans.models.provenance.schemas import SourceMap, TextAnchor
from score_trans.models.score import OCRTextBlock
from score_trans.models.settings.config import ToolConfig
from score_trans.services.files.upload_service import UploadService
from score_trans.services.ocr.providers import MockOCRProvider
from score_trans.services.render import PublicationRenderService


class FakeRecognizer:
    def __init__(self, expected_source: Path, recognized: Path) -> None:
        self.expected_source = expected_source
        self.recognized = recognized
        self.calls = []

    def execute(self, input_file: Path, output_dir: Path, config: ToolConfig) -> Path:
        self.calls.append((input_file, output_dir, config))
        assert input_file == self.expected_source.resolve()
        assert output_dir.name == "omr"
        assert config.audiveris_path == "fake-audiveris"
        return self.recognized


class EmptyRenderer:
    def render_scores_a4_svg_pages(self, *args, **kwargs) -> list[Path]:
        return []


class CapturingRenderer:
    def __init__(self) -> None:
        self.kwargs: dict[str, object] = {}

    def render_scores_a4_svg_pages(self, *args, **kwargs):
        self.kwargs = dict(kwargs)
        return PublicationRenderService().render_scores_a4_svg_pages(*args, **kwargs)


class StaticSettings:
    def __init__(self, config: ToolConfig, *, enable_omr_ocr: bool = True) -> None:
        self.config = config
        self.enable_omr_ocr = enable_omr_ocr

    def load(self) -> ToolConfig:
        return self.config

    def get_bool(self, key: str, default: bool = False) -> bool:
        if key == "enable_omr_ocr":
            return self.enable_omr_ocr
        return default


class EmptyOutputPipeline:
    def __init__(self, outputs: ScorePipelineOutputs) -> None:
        self.outputs = outputs

    def execute(self, *args, **kwargs) -> ScorePipelineOutputs:
        return self.outputs


class CapturingPipeline:
    def __init__(self, outputs: ScorePipelineOutputs) -> None:
        self.outputs = outputs
        self.enable_omr_ocr: bool | None = None

    def execute(self, *args, **kwargs) -> ScorePipelineOutputs:
        self.enable_omr_ocr = kwargs["enable_omr_ocr"]
        return self.outputs


def test_unmapped_omr_warnings_identify_noteheads_without_text_anchors() -> None:
    source_map = SourceMap.model_validate(
        {
            "version": 1,
            "sheets": [
                {
                    "sheet_index": 1,
                    "width": 100,
                    "height": 100,
                    "overlay_file": "overlay.png",
                    "elements": [
                        {
                            "source_id": "s1:i10",
                            "inter_id": 10,
                            "shape": "NOTEHEAD_BLACK",
                            "grade": 0.9,
                            "bounds": {"x": 0, "y": 0, "width": 10, "height": 10},
                            "hit_path": "M0 0",
                            "musicxml_locator": {
                                "attribute": "id",
                                "contains": "n-s1-i10",
                            },
                        },
                        {
                            "source_id": "s1:i11",
                            "inter_id": 11,
                            "shape": "SHARP",
                            "grade": 0.9,
                            "bounds": {"x": 0, "y": 0, "width": 10, "height": 10},
                            "hit_path": "M0 0",
                            "musicxml_locator": {
                                "attribute": "id",
                                "contains": "a-s1-i11",
                            },
                        },
                    ],
                }
            ],
        }
    )

    warnings = _unmapped_omr_warnings(
        source_map,
        [TextAnchor(source_id="s1:i11", start_utf16=0, end_utf16=1, role="accidental")],
    )

    assert warnings == [
        "第 1 页有 1 个识别音头未进入 MusicXML，未自动写入简谱；请修正原谱后重新识别。"
    ]


def test_pipeline_auxiliary_failures_are_logged_and_degraded(
    tmp_path: Path, monkeypatch, caplog
) -> None:
    class BrokenOverlayService:
        def generate_overlay_svgs(self, _output_dir: Path) -> list[Path]:
            raise RuntimeError("overlay failure")

    def fail_rglob(_path: Path, _pattern: str):
        raise OSError("directory failure")

    monkeypatch.setattr(Path, "rglob", fail_rglob)

    assert _generate_overlay(BrokenOverlayService(), tmp_path) is None
    assert _find_omr_file(tmp_path) is None
    assert "生成 OMR SVG 叠加层失败" in caplog.text
    assert "查找 OMR 文件失败" in caplog.text


def test_full_pipeline_writes_pipeline_outputs(tmp_path) -> None:
    source = tmp_path / "scan.pdf"
    source.write_bytes(b"%PDF-1.4")
    recognized = tmp_path / "audiveris-output.musicxml"
    recognized.write_text(jianpu_to_musicxml("1=C\n4/4\n1 2 |"), encoding="utf-8")
    recognizer = FakeRecognizer(source, recognized)

    outputs = FullPipelineAction(recognizer=recognizer).execute(
        source,
        tmp_path / "out",
        config=ToolConfig(audiveris_path="fake-audiveris"),
        target_key="C",
        title="Pipeline Test",
    )

    assert outputs.musicxml_path.name == "scan.musicxml"
    assert outputs.musicxml_path.exists()
    jianpu_text = outputs.jianpu_text_path.read_text(encoding="utf-8")
    # 单声部也输出 @part 标记（F4 修复后的一致行为）
    assert jianpu_text.startswith(
        '// @part 1 name="Music"\ntitle=Pipeline Test\ntempo=120\n1=C\n4/4\n1 2 |'
    )
    assert "h0" not in jianpu_text
    svg = outputs.jianpu_svg_path.read_text(encoding="utf-8")
    assert "Pipeline Test" in svg
    assert ">1</text>" in svg
    assert recognizer.calls


def test_full_pipeline_forwards_a4_layout_controls(tmp_path: Path) -> None:
    source = tmp_path / "scan.pdf"
    source.write_bytes(b"%PDF-1.4")
    recognized = tmp_path / "audiveris-output.musicxml"
    recognized.write_text(jianpu_to_musicxml("1=C\n4/4\n1 2 |"), encoding="utf-8")
    renderer = CapturingRenderer()

    FullPipelineAction(
        recognizer=FakeRecognizer(source, recognized), renderer=renderer
    ).execute(
        source,
        tmp_path / "out",
        config=ToolConfig(audiveris_path="fake-audiveris"),
        content_scale_percent=75,
        system_gap_percent=88,
        short_note_gap_percent=85,
        beat_gap_percent=140,
    )

    assert renderer.kwargs["content_scale_percent"] == 75
    assert renderer.kwargs["system_gap_percent"] == 88
    assert renderer.kwargs["short_note_gap_percent"] == 85
    assert renderer.kwargs["beat_gap_percent"] == 140


def test_full_pipeline_can_hide_measure_numbers(tmp_path) -> None:
    source = tmp_path / "scan.pdf"
    source.write_bytes(b"%PDF-1.4")
    recognized = tmp_path / "audiveris-output.musicxml"
    recognized.write_text(jianpu_to_musicxml("1=C\n4/4\n1 2 |"), encoding="utf-8")
    recognizer = FakeRecognizer(source, recognized)

    outputs = FullPipelineAction(recognizer=recognizer).execute(
        source,
        tmp_path / "out",
        config=ToolConfig(audiveris_path="fake-audiveris"),
        target_key="C",
        measure_number_mode="none",
        title="Pipeline Test",
    )

    svg = outputs.jianpu_svg_path.read_text(encoding="utf-8")
    assert "Pipeline Test" in svg
    assert 'class="measure-no"' not in svg


def test_full_pipeline_rejects_empty_render_output(tmp_path: Path) -> None:
    source = tmp_path / "scan.pdf"
    source.write_bytes(b"%PDF-1.4")
    recognized = tmp_path / "audiveris-output.musicxml"
    recognized.write_text(jianpu_to_musicxml("1=C\n4/4\n1 2 |"), encoding="utf-8")

    with pytest.raises(RenderError, match="未生成任何简谱 SVG 页面"):
        FullPipelineAction(
            recognizer=FakeRecognizer(source, recognized),
            renderer=EmptyRenderer(),
        ).execute(
            source,
            tmp_path / "out",
            config=ToolConfig(audiveris_path="fake-audiveris"),
        )


def test_pipeline_actions_do_not_register_partial_outputs_when_render_is_empty(
    tmp_path: Path,
) -> None:
    work_dir = tmp_path / "work"
    input_path = tmp_path / "scan.pdf"
    musicxml_path = tmp_path / "scan.musicxml"
    text_path = tmp_path / "scan.txt"
    input_path.write_bytes(b"%PDF-1.4")
    musicxml_path.write_text("<score-partwise/>", encoding="utf-8")
    text_path.write_text("1=C\n4/4\n1 |", encoding="utf-8")
    uploads = UploadService(ToolConfig(work_dir=work_dir))
    outputs = ScorePipelineOutputs(
        input_path=input_path,
        musicxml_path=musicxml_path,
        jianpu_text_path=text_path,
        jianpu_svg_paths=[],
        render_map_paths=[],
    )
    actions = PipelineActions(
        uploads=uploads,
        settings=StaticSettings(ToolConfig(work_dir=work_dir)),
        pipeline=EmptyOutputPipeline(outputs),
    )

    with pytest.raises(RenderError, match="未生成任何简谱 SVG 页面"):
        actions.run_pipeline_from_path(input_path)

    assert list(uploads.base_dir.iterdir()) == []


def test_pipeline_actions_read_compressed_mxl_as_musicxml(tmp_path: Path) -> None:
    work_dir = tmp_path / "work"
    input_path = tmp_path / "scan.png"
    musicxml_path = tmp_path / "scan.mxl"
    text_path = tmp_path / "scan.txt"
    svg_path = tmp_path / "scan.svg"
    input_path.write_bytes(b"png")
    xml = '<score-partwise version="4.0"/>'
    with ZipFile(musicxml_path, "w") as archive:
        archive.writestr(
            "META-INF/container.xml",
            """<container><rootfiles><rootfile full-path="score.xml"/></rootfiles></container>""",
        )
        archive.writestr("score.xml", xml)
    text_path.write_text("1=C\n4/4\n1 |", encoding="utf-8")
    svg_path.write_text("<svg/>", encoding="utf-8")
    uploads = UploadService(ToolConfig(work_dir=work_dir))
    actions = PipelineActions(
        uploads=uploads,
        settings=StaticSettings(ToolConfig(work_dir=work_dir)),
        pipeline=EmptyOutputPipeline(
            ScorePipelineOutputs(
                input_path=input_path,
                musicxml_path=musicxml_path,
                jianpu_text_path=text_path,
                jianpu_svg_paths=[svg_path],
                render_map_paths=[],
                warnings=["OMR warning"],
            )
        ),
    )

    response = actions.run_pipeline_from_path(input_path)

    assert response.musicxml_text == xml
    assert response.warnings == ["OMR warning"]


def test_full_pipeline_runs_ocr_for_image_and_outputs_a4_layout(tmp_path) -> None:
    source = tmp_path / "scan.png"
    Image.new("RGB", (320, 480), "white").save(source)
    recognized = tmp_path / "audiveris-output.musicxml"
    recognized.write_text(jianpu_to_musicxml("1=C\n4/4\n1 2 |"), encoding="utf-8")
    recognizer = FakeRecognizer(source, recognized)
    provider = MockOCRProvider(
        [
            OCRTextBlock(
                "原谱标题", bbox=(24, 18, 120, 42), confidence=0.95, role="title"
            ),
            OCRTextBlock("42", bbox=(8, 10, 24, 28), role="measure_number"),
        ]
    )

    outputs = FullPipelineAction(recognizer=recognizer).execute(
        source,
        tmp_path / "out",
        config=ToolConfig(audiveris_path="fake-audiveris"),
        target_key="C",
        ocr_provider=provider,
        enable_omr_ocr=True,
    )

    svg = outputs.jianpu_svg_path.read_text(encoding="utf-8")
    assert provider.calls == [source.resolve()]
    assert outputs.jianpu_svg_paths == [outputs.jianpu_svg_path]
    assert 'width="1240"' in svg
    assert 'height="1754"' in svg
    assert 'viewBox="0 0 1240 1754"' in svg
    ocr_blocks = json.loads(outputs.ocr_text)
    assert [block["text"] for block in ocr_blocks] == ["原谱标题"]
    assert [item.text for item in outputs.text_attachments] == ["原谱标题"]
    assert outputs.text_attachments[0].anchor.kind == "score_start"
    assert "text_attachments" in PipelineResponse.model_json_schema()["properties"]


def test_full_pipeline_skips_ocr_but_keeps_conversion_outputs_when_disabled(
    tmp_path: Path,
) -> None:
    source = tmp_path / "scan.png"
    Image.new("RGB", (320, 480), "white").save(source)
    recognized = tmp_path / "audiveris-output.musicxml"
    recognized.write_text(jianpu_to_musicxml("1=C\n4/4\n1 2 |"), encoding="utf-8")
    provider = MockOCRProvider([OCRTextBlock("不应被调用", role="title")])

    outputs = FullPipelineAction(
        recognizer=FakeRecognizer(source, recognized),
    ).execute(
        source,
        tmp_path / "out",
        config=ToolConfig(audiveris_path="fake-audiveris"),
        enable_omr_ocr=False,
        ocr_provider=provider,
    )

    assert provider.calls == []
    assert outputs.musicxml_path.exists()
    assert outputs.jianpu_text_path.exists()
    assert outputs.jianpu_svg_path.exists()
    assert outputs.ocr_text == ""
    assert outputs.text_attachments == []
    assert isinstance(outputs.text_anchors, list)
    assert outputs.text_hash


def test_pipeline_uses_persisted_ocr_setting_snapshot(tmp_path: Path) -> None:
    work_dir = tmp_path / "work"
    input_path = tmp_path / "scan.pdf"
    musicxml_path = tmp_path / "scan.musicxml"
    text_path = tmp_path / "scan.txt"
    svg_path = tmp_path / "scan.svg"
    input_path.write_bytes(b"%PDF-1.4")
    musicxml_path.write_text("<score-partwise/>", encoding="utf-8")
    text_path.write_text("1=C\n4/4\n1 |", encoding="utf-8")
    svg_path.write_text("<svg/>", encoding="utf-8")
    outputs = ScorePipelineOutputs(
        input_path=input_path,
        musicxml_path=musicxml_path,
        jianpu_text_path=text_path,
        jianpu_svg_paths=[svg_path],
        render_map_paths=[],
    )
    pipeline = CapturingPipeline(outputs)
    actions = PipelineActions(
        uploads=UploadService(ToolConfig(work_dir=work_dir)),
        settings=StaticSettings(
            ToolConfig(work_dir=work_dir, enable_omr_ocr=False),
            enable_omr_ocr=False,
        ),
        pipeline=pipeline,
    )

    actions.run_pipeline_from_path(input_path)

    assert pipeline.enable_omr_ocr is False
