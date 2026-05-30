from pathlib import Path

from score_trans.cli.commands import build_parser
from score_trans.services.settings import ToolConfig
from score_trans.use_cases.full_pipeline import ScorePipelineOutputs
from score_trans.viewmodels.main_window_vm import MainWindowDependencies, MainWindowViewModel


class FakeSettingsService:
    def __init__(self, work_dir: Path) -> None:
        self.work_dir = work_dir

    def load(self) -> ToolConfig:
        return ToolConfig(audiveris_path="audiveris-test", musescore_path="musescore-test", work_dir=self.work_dir)


class FakeFullPipelineUseCase:
    def __init__(self, musicxml_path: Path, text_path: Path, svg_path: Path) -> None:
        self.outputs = ScorePipelineOutputs(
            input_path=Path("scan.pdf"),
            musicxml_path=musicxml_path,
            jianpu_text_path=text_path,
            jianpu_svg_path=svg_path,
        )
        self.calls = []

    def execute(self, input_path, output_dir, *, config, target_key, start_measure_number, title=None):
        self.calls.append((Path(input_path), Path(output_dir), config, target_key, start_measure_number, title))
        return self.outputs


def test_cli_parser_exposes_mvvm_use_case_commands() -> None:
    parser = build_parser()

    args = parser.parse_args(["recognize", "scan.pdf", "-o", "out", "--target-key", "G"])

    assert args.command == "recognize"
    assert args.output_dir == Path("out")
    assert args.target_key == "G"


def test_main_window_view_model_runs_full_pipeline_without_view(tmp_path) -> None:
    musicxml = tmp_path / "score.musicxml"
    text = tmp_path / "score_jianpu.txt"
    svg = tmp_path / "score_jianpu.svg"
    musicxml.write_text("<score-partwise/>", encoding="utf-8")
    text.write_text("key=C\ntime=4/4\n1 2 |", encoding="utf-8")
    svg.write_text("<svg/>", encoding="utf-8")
    full_pipeline = FakeFullPipelineUseCase(musicxml, text, svg)
    vm = MainWindowViewModel(
        MainWindowDependencies(
            settings_service=FakeSettingsService(tmp_path),
            full_pipeline=full_pipeline,
        )
    )
    logs: list[str] = []
    vm.log_added.connect(logs.append)

    vm.set_input_file(tmp_path / "scan.pdf")
    vm.set_target_key("G")
    vm.set_start_measure_text("12")
    ok = vm.recognize_and_export_jianpu(tmp_path / "out")

    assert ok is True
    assert vm.musicxml_file == musicxml
    assert vm.musicxml_text == "<score-partwise/>"
    assert vm.jianpu_text.startswith("key=C")
    assert full_pipeline.calls[0][3:5] == ("G", 12)
    assert any("简谱谱面" in item for item in logs)


def test_view_layer_does_not_import_business_modules() -> None:
    source = Path("src/score_trans/views/main_window.py").read_text(encoding="utf-8")

    assert "from ..services.external_tools" not in source
    assert "from ..domain.jianpu" not in source
    assert "from ..domain.musicxml" not in source
    assert "from ..services.rendering" not in source


def test_top_level_package_has_no_legacy_compat_modules() -> None:
    files = {path.name for path in Path("src/score_trans").glob("*.py")}

    assert files == {"__init__.py", "__main__.py"}
