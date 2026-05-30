from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from ..services.file_service import FileService
from ..services.settings import ToolConfig
from ..services.settings_service import SettingsService
from ..use_cases import (
    ConvertJianpuToMusicXmlUseCase,
    ConvertMusicXmlToJianpuUseCase,
    ExportScoreUseCase,
    FullPipelineUseCase,
    RecognizeScoreUseCase,
    RenderMusicXmlJianpuUseCase,
)
from .base import parse_optional_int


@dataclass(slots=True)
class MainWindowDependencies:
    settings_service: SettingsService = field(default_factory=SettingsService)
    file_service: FileService = field(default_factory=FileService)
    recognize_score: RecognizeScoreUseCase = field(default_factory=RecognizeScoreUseCase)
    full_pipeline: FullPipelineUseCase = field(default_factory=FullPipelineUseCase)
    convert_to_jianpu: ConvertMusicXmlToJianpuUseCase = field(default_factory=ConvertMusicXmlToJianpuUseCase)
    convert_to_musicxml: ConvertJianpuToMusicXmlUseCase = field(default_factory=ConvertJianpuToMusicXmlUseCase)
    render_musicxml_jianpu: RenderMusicXmlJianpuUseCase = field(default_factory=RenderMusicXmlJianpuUseCase)
    export_score: ExportScoreUseCase = field(default_factory=ExportScoreUseCase)


class MainWindowViewModel(QObject):
    input_file_changed = Signal(str)
    musicxml_file_changed = Signal(str)
    musicxml_text_changed = Signal(str)
    jianpu_text_changed = Signal(str)
    log_added = Signal(str)
    error_occurred = Signal(str)
    busy_changed = Signal(bool)

    def __init__(self, dependencies: MainWindowDependencies | None = None) -> None:
        super().__init__()
        self.dependencies = dependencies or MainWindowDependencies()
        self.config: ToolConfig = self.dependencies.settings_service.load()
        self.input_file: Path | None = None
        self.musicxml_file: Path | None = None
        self.musicxml_text = ""
        self.jianpu_text = ""
        self.target_key = "C"
        self.start_measure_text = ""
        self.busy = False

    def set_tool_paths(self, audiveris_path: str, musescore_path: str, java_home: str) -> None:
        self.config.audiveris_path = audiveris_path.strip() or "audiveris"
        self.config.musescore_path = musescore_path.strip() or "musescore"
        self.config.java_home = java_home.strip()

    def set_target_key(self, value: str) -> None:
        self.target_key = value.strip() or "C"

    def set_start_measure_text(self, value: str) -> None:
        self.start_measure_text = value.strip()

    def set_input_file(self, path: str | Path) -> None:
        self.input_file = Path(path)
        self.input_file_changed.emit(str(self.input_file))

    def set_musicxml_text(self, text: str, *, emit: bool = False) -> None:
        self.musicxml_text = text
        if emit:
            self.musicxml_text_changed.emit(text)

    def set_jianpu_text(self, text: str, *, emit: bool = False) -> None:
        self.jianpu_text = text
        if emit:
            self.jianpu_text_changed.emit(text)

    def load_musicxml(self, path: str | Path) -> bool:
        return self._execute(
            lambda: self._load_musicxml(path),
            success_log=f"已打开 MusicXML：{Path(path)}",
        )

    def recognize_musicxml(self) -> bool:
        if self.input_file is None:
            return self._error("请先选择图片或 PDF。")
        return self._execute(self._recognize_musicxml)

    def recognize_and_show_jianpu(self) -> bool:
        if self.input_file is None:
            return self._error("请先选择图片或 PDF。")
        return self._execute(self._recognize_and_show_jianpu, success_log="已识别并转换为简谱。")

    def recognize_and_export_jianpu(self, output_dir: str | Path) -> bool:
        if self.input_file is None:
            return self._error("请先选择图片或 PDF。")
        return self._execute(lambda: self._recognize_and_export_jianpu(output_dir))

    def convert_musicxml_to_jianpu(self) -> bool:
        if self.musicxml_file is None:
            return self._error("请先识别或打开 MusicXML。")
        return self._execute(self._convert_musicxml_to_jianpu, success_log="已转换为简谱。")

    def convert_jianpu_to_musicxml(self) -> bool:
        return self._execute(self._convert_jianpu_to_musicxml)

    def save_jianpu(self, path: str | Path) -> bool:
        return self._execute(
            lambda: self.dependencies.file_service.write_text(path, self.jianpu_text),
            success_log=f"已保存简谱：{path}",
        )

    def save_musicxml(self, path: str | Path) -> bool:
        if not self.musicxml_text.strip():
            return self._error("没有可保存的 MusicXML。")
        return self._execute(
            lambda: self._save_musicxml(path),
            success_log=f"已保存 MusicXML：{path}",
        )

    def save_jianpu_svg(self, path: str | Path) -> bool:
        if self.musicxml_file is None:
            return self._error("请先识别或打开 MusicXML。")
        return self._execute(
            lambda: self.dependencies.render_musicxml_jianpu.execute(
                self.musicxml_file,
                path,
                target_key=self.target_key,
                start_measure_number=self.start_measure_number,
            ),
            success_log=f"已导出简谱谱面：{path}",
        )

    def export_musicxml(self, path: str | Path) -> bool:
        if self.musicxml_file is None:
            return self._error("请先准备 MusicXML。")
        return self._execute(
            lambda: self.dependencies.export_score.execute(self.musicxml_file, path, self.config),
            success_log=f"导出完成：{path}",
        )

    @property
    def start_measure_number(self) -> int | None:
        return parse_optional_int(self.start_measure_text, "起始小节号")

    def _load_musicxml(self, path: str | Path) -> None:
        musicxml_path = Path(path)
        self.musicxml_file = musicxml_path
        self.musicxml_file_changed.emit(str(musicxml_path))
        self.set_musicxml_text(self.dependencies.file_service.read_musicxml_text(musicxml_path), emit=True)

    def _recognize_musicxml(self) -> None:
        assert self.input_file is not None
        output = self.dependencies.recognize_score.execute(
            self.input_file,
            self.config.work_dir / "audiveris",
            self.config,
        )
        self.musicxml_file = output
        self.musicxml_file_changed.emit(str(output))
        self.set_musicxml_text(self.dependencies.file_service.read_musicxml_text(output), emit=True)
        self._log(f"OMR 完成：{output}")

    def _recognize_and_show_jianpu(self) -> None:
        assert self.input_file is not None
        self._recognize_musicxml()
        self._convert_musicxml_to_jianpu()

    def _recognize_and_export_jianpu(self, output_dir: str | Path) -> None:
        assert self.input_file is not None
        outputs = self.dependencies.full_pipeline.execute(
            self.input_file,
            output_dir,
            config=self.config,
            target_key=self.target_key,
            start_measure_number=self.start_measure_number,
        )
        self.musicxml_file = outputs.musicxml_path
        self.musicxml_file_changed.emit(str(outputs.musicxml_path))
        self.set_musicxml_text(self.dependencies.file_service.read_musicxml_text(outputs.musicxml_path), emit=True)
        self.set_jianpu_text(self.dependencies.file_service.read_text(outputs.jianpu_text_path), emit=True)
        self._log(f"MusicXML：{outputs.musicxml_path}")
        self._log(f"简谱文本：{outputs.jianpu_text_path}")
        self._log(f"简谱谱面：{outputs.jianpu_svg_path}")

    def _convert_musicxml_to_jianpu(self) -> None:
        assert self.musicxml_file is not None
        jianpu = self.dependencies.convert_to_jianpu.execute(
            self.musicxml_file,
            target_key=self.target_key,
            start_measure_number=self.start_measure_number,
        )
        self.set_jianpu_text(jianpu, emit=True)

    def _convert_jianpu_to_musicxml(self) -> None:
        xml = self.dependencies.convert_to_musicxml.execute_text(self.jianpu_text)
        out = self.config.work_dir / "jianpu.musicxml"
        self.dependencies.file_service.write_text(out, xml)
        self.musicxml_file = out
        self.musicxml_file_changed.emit(str(out))
        self.set_musicxml_text(xml, emit=True)
        self._log(f"已生成 MusicXML：{out.resolve()}")

    def _save_musicxml(self, path: str | Path) -> None:
        target = self.dependencies.file_service.write_text(path, self.musicxml_text)
        self.musicxml_file = target
        self.musicxml_file_changed.emit(str(target))

    def _execute(self, action, *, success_log: str | None = None) -> bool:
        self._set_busy(True)
        try:
            action()
        except Exception as exc:
            self._set_busy(False)
            return self._error(str(exc))
        self._set_busy(False)
        if success_log:
            self._log(success_log)
        return True

    def _set_busy(self, value: bool) -> None:
        if self.busy == value:
            return
        self.busy = value
        self.busy_changed.emit(value)

    def _log(self, message: str) -> None:
        self.log_added.emit(message)

    def _error(self, message: str) -> bool:
        self.error_occurred.emit(message)
        self.log_added.emit(message)
        return False
