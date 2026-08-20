import json
from pathlib import Path
from zipfile import ZipFile

from PIL import Image
import pytest

from score_trans.domain.jianpu import jianpu_to_musicxml
from score_trans.exec.pipeline.actions import (
    FullPipelineAction,
    PipelineActions,
    ScorePipelineOutputs,
    _find_omr_file,
    _generate_overlay,
)
from score_trans.models.common.errors import RenderError
from score_trans.models.pipeline.schemas import PipelineResponse
from score_trans.models.score import OCRTextBlock
from score_trans.models.settings.config import ToolConfig
from score_trans.services.files.upload_service import UploadService
from score_trans.services.ocr.providers import MockOCRProvider


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


class StaticSettings:
    def __init__(self, config: ToolConfig) -> None:
        self.config = config

    def load(self) -> ToolConfig:
        return self.config


class EmptyOutputPipeline:
    def __init__(self, outputs: ScorePipelineOutputs) -> None:
        self.outputs = outputs

    def execute(self, *args, **kwargs) -> ScorePipelineOutputs:
        return self.outputs


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
    assert outputs.jianpu_text_path.read_text(encoding="utf-8").startswith(
        "title=Pipeline Test\n1=C\n4/4"
    )
    assert "h0" in outputs.jianpu_text_path.read_text(encoding="utf-8")
    svg = outputs.jianpu_svg_path.read_text(encoding="utf-8")
    assert "Pipeline Test" in svg
    assert ">1</text>" in svg
    assert recognizer.calls


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
            )
        ),
    )

    response = actions.run_pipeline_from_path(input_path)

    assert response.musicxml_text == xml


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
