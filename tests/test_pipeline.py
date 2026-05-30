from pathlib import Path

from score_trans.domain.jianpu import jianpu_to_musicxml
from score_trans.domain.models import OCRTextBlock
from score_trans.services.ocr_provider import MockOCRProvider
from score_trans.services.settings import ToolConfig
from score_trans.use_cases.convert_to_jianpu import ConvertMusicXmlToJianpuUseCase
from score_trans.use_cases.full_pipeline import FullPipelineUseCase


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


def test_full_pipeline_writes_pipeline_outputs(tmp_path) -> None:
    source = tmp_path / "scan.pdf"
    source.write_bytes(b"%PDF-1.4")
    recognized = tmp_path / "audiveris-output.musicxml"
    recognized.write_text(jianpu_to_musicxml("key=C\ntime=4/4\n1 2 |"), encoding="utf-8")
    recognizer = FakeRecognizer(source, recognized)

    outputs = FullPipelineUseCase(recognizer=recognizer).execute(
        source,
        tmp_path / "out",
        config=ToolConfig(audiveris_path="fake-audiveris"),
        target_key="C",
        start_measure_number=118,
        title="Pipeline Test",
    )

    assert outputs.musicxml_path.name == "scan.musicxml"
    assert outputs.musicxml_path.exists()
    assert outputs.jianpu_text_path.read_text(encoding="utf-8").startswith("key=C\ntime=4/4")
    assert "0-" in outputs.jianpu_text_path.read_text(encoding="utf-8")
    svg = outputs.jianpu_svg_path.read_text(encoding="utf-8")
    assert "Pipeline Test" in svg
    assert ">118</text>" in svg
    assert recognizer.calls


def test_build_score_from_musicxml_can_apply_ocr_measure_numbers(tmp_path) -> None:
    musicxml = tmp_path / "score.musicxml"
    image = tmp_path / "score.png"
    musicxml.write_text(jianpu_to_musicxml("key=C\ntime=4/4\n1 2 | 3 4 |"), encoding="utf-8")
    image.write_bytes(b"fake image")
    provider = MockOCRProvider([OCRTextBlock("42", role="measure_number")])

    score = ConvertMusicXmlToJianpuUseCase().build_score(musicxml, image_path=image, ocr_provider=provider)

    assert [measure.display_number for measure in score.measures] == [42, 43]
    assert provider.calls == [image]
