from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..viewmodels import MainWindowViewModel


class MainWindow(QMainWindow):
    def __init__(self, view_model: MainWindowViewModel | None = None) -> None:
        super().__init__()
        self.vm = view_model or MainWindowViewModel()
        self._syncing_jianpu = False
        self.setWindowTitle("Score Trans 五线谱 / 简谱互转")
        self.resize(1200, 800)

        root = QWidget()
        layout = QVBoxLayout(root)
        layout.addWidget(self._build_settings())
        layout.addWidget(self._build_tabs(), 1)
        self.setCentralWidget(root)
        self._connect_view_model()

    # ------------------------------------------------------------------
    # Settings panel
    # ------------------------------------------------------------------

    def _build_settings(self) -> QGroupBox:
        box = QGroupBox("外部工具")
        grid = QGridLayout(box)
        self.audiveris_edit = QLineEdit(self.vm.config.audiveris_path)
        self.musescore_edit = QLineEdit(self.vm.config.musescore_path)
        self.java_home_edit = QLineEdit(self.vm.config.java_home)
        self.target_key_edit = QLineEdit(self.vm.target_key)
        self.start_measure_edit = QLineEdit(self.vm.start_measure_text)
        self.start_measure_edit.setPlaceholderText("留空则使用 MusicXML 小节号")
        grid.addWidget(QLabel("Audiveris"), 0, 0)
        grid.addWidget(self.audiveris_edit, 0, 1)
        grid.addWidget(QLabel("MuseScore"), 1, 0)
        grid.addWidget(self.musescore_edit, 1, 1)
        grid.addWidget(QLabel("JDK / JAVA_HOME"), 2, 0)
        grid.addWidget(self.java_home_edit, 2, 1)
        grid.addWidget(QLabel("简谱调"), 3, 0)
        grid.addWidget(self.target_key_edit, 3, 1)
        grid.addWidget(QLabel("起始小节号"), 4, 0)
        grid.addWidget(self.start_measure_edit, 4, 1)
        return box

    # ------------------------------------------------------------------
    # Tabs
    # ------------------------------------------------------------------

    def _build_tabs(self) -> QTabWidget:
        tabs = QTabWidget()
        tabs.addTab(self._build_comparison_tab(), "五线谱 / 简谱对照")
        tabs.addTab(self._build_jianpu_tab(), "简谱互转")
        tabs.addTab(self._build_export_tab(), "导出")
        return tabs

    # ------------------------------------------------------------------
    # Tab 1 — Score / Jianpu comparison
    # ------------------------------------------------------------------

    def _build_comparison_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        # --- toolbar ---
        actions = QHBoxLayout()
        open_btn = QPushButton("选择图片或 PDF")
        open_btn.clicked.connect(self.choose_input)
        recognize_btn = QPushButton("识别为简谱")
        recognize_btn.clicked.connect(self.recognize_and_show_jianpu)
        save_jianpu_btn = QPushButton("保存简谱")
        save_jianpu_btn.clicked.connect(self.save_jianpu)
        save_svg_btn = QPushButton("导出 SVG")
        save_svg_btn.clicked.connect(self.save_jianpu_svg)
        load_xml_btn = QPushButton("打开 MusicXML")
        load_xml_btn.clicked.connect(self.load_musicxml)
        actions.addWidget(open_btn)
        actions.addWidget(recognize_btn)
        actions.addWidget(save_jianpu_btn)
        actions.addWidget(save_svg_btn)
        actions.addWidget(load_xml_btn)
        actions.addStretch(1)

        self.input_label = QLabel("未选择文件")
        self.input_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        # --- splitter: image | jianpu editor ---
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # left: score image
        image_box = QGroupBox("五线谱")
        image_layout = QVBoxLayout(image_box)
        self.score_image_label = QLabel("请选择五线谱图片")
        self.score_image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.score_image_label.setMinimumSize(200, 150)
        image_layout.addWidget(self.score_image_label)
        splitter.addWidget(image_box)

        # right: jianpu editor
        jianpu_box = QGroupBox("简谱编辑")
        jianpu_layout = QVBoxLayout(jianpu_box)
        self.omr_jianpu_edit = QPlainTextEdit()
        self.omr_jianpu_edit.setPlaceholderText(
            "识别后的简谱会显示在这里，也可以直接编辑。\n\n"
            "key=C\ntime=4/4\n1 2 3 4 | 5 6 7 1' |"
        )
        jianpu_layout.addWidget(self.omr_jianpu_edit)
        splitter.addWidget(jianpu_box)

        splitter.setSizes([550, 450])

        layout.addLayout(actions)
        layout.addWidget(self.input_label)
        layout.addWidget(splitter, 1)
        return page

    # ------------------------------------------------------------------
    # Tab 2 — Jianpu standalone editor
    # ------------------------------------------------------------------

    def _build_jianpu_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        actions = QHBoxLayout()
        to_jianpu_btn = QPushButton("MusicXML -> 简谱")
        to_jianpu_btn.clicked.connect(self.convert_musicxml_to_jianpu)
        to_xml_btn = QPushButton("简谱 -> MusicXML")
        to_xml_btn.clicked.connect(self.convert_jianpu_to_musicxml)
        save_jianpu_btn = QPushButton("保存简谱")
        save_jianpu_btn.clicked.connect(self.save_jianpu)
        save_svg_btn = QPushButton("导出简谱谱面 SVG")
        save_svg_btn.clicked.connect(self.save_jianpu_svg)
        actions.addWidget(to_jianpu_btn)
        actions.addWidget(to_xml_btn)
        actions.addWidget(save_jianpu_btn)
        actions.addWidget(save_svg_btn)
        actions.addStretch(1)
        self.jianpu_edit = QPlainTextEdit()
        self.jianpu_edit.setPlaceholderText("key=C\ntime=4/4\n1 2 3 4 | 5 6 7 1' |")
        layout.addLayout(actions)
        layout.addWidget(self.jianpu_edit, 1)
        return page

    # ------------------------------------------------------------------
    # Tab 3 — Export
    # ------------------------------------------------------------------

    def _build_export_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        actions = QHBoxLayout()
        save_xml_btn = QPushButton("保存 MusicXML")
        save_xml_btn.clicked.connect(self.save_musicxml)
        export_btn = QPushButton("MuseScore 导出")
        export_btn.clicked.connect(self.export_musicxml)
        actions.addWidget(save_xml_btn)
        actions.addWidget(export_btn)
        actions.addStretch(1)
        self.log_edit = QPlainTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setPlaceholderText("操作日志")
        layout.addLayout(actions)
        layout.addWidget(self.log_edit, 1)
        return page

    # ------------------------------------------------------------------
    # ViewModel connections
    # ------------------------------------------------------------------

    def _connect_view_model(self) -> None:
        # settings
        self.audiveris_edit.textChanged.connect(self._sync_tool_paths)
        self.musescore_edit.textChanged.connect(self._sync_tool_paths)
        self.java_home_edit.textChanged.connect(self._sync_tool_paths)
        self.target_key_edit.textChanged.connect(self.vm.set_target_key)
        self.start_measure_edit.textChanged.connect(self.vm.set_start_measure_text)

        # jianpu editors — bidirectional sync
        self.jianpu_edit.textChanged.connect(self._on_jianpu_tab_changed)
        self.omr_jianpu_edit.textChanged.connect(self._on_omr_jianpu_changed)

        # vm → view
        self.vm.input_file_changed.connect(self._on_input_file_changed)
        self.vm.jianpu_text_changed.connect(self._set_jianpu_preview)
        self.vm.log_added.connect(self.log_edit.appendPlainText)
        self.vm.error_occurred.connect(self._warn)
        self.vm.busy_changed.connect(self._set_busy)

    # ------------------------------------------------------------------
    # User actions
    # ------------------------------------------------------------------

    def choose_input(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择乐谱图片或 PDF",
            "",
            "Scores (*.pdf *.png *.jpg *.jpeg *.tif *.tiff);;All files (*.*)",
        )
        if path:
            self.vm.set_input_file(path)

    def load_musicxml(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "打开 MusicXML",
            "",
            "MusicXML (*.musicxml *.xml *.mxl);;All files (*.*)",
        )
        if path:
            self.vm.load_musicxml(path)

    def recognize_and_show_jianpu(self) -> None:
        self._sync_tool_paths()
        self.vm.recognize_and_show_jianpu()

    def recognize_and_export_jianpu(self) -> None:
        output_dir = QFileDialog.getExistingDirectory(
            self,
            "选择输出目录",
            str(self.vm.config.work_dir / "converted"),
        )
        if output_dir:
            self._sync_tool_paths()
            self.vm.recognize_and_export_jianpu(output_dir)

    def convert_musicxml_to_jianpu(self) -> None:
        self.vm.convert_musicxml_to_jianpu()

    def convert_jianpu_to_musicxml(self) -> None:
        self.vm.convert_jianpu_to_musicxml()

    def save_jianpu(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "保存简谱", "jianpu.txt", "Text (*.txt)")
        if path:
            self.vm.save_jianpu(path)

    def save_jianpu_svg(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "导出简谱谱面", "jianpu.svg", "SVG (*.svg)")
        if path:
            self.vm.save_jianpu_svg(path)

    def save_musicxml(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "保存 MusicXML", "score.musicxml", "MusicXML (*.musicxml)")
        if path:
            self.vm.save_musicxml(path)

    def export_musicxml(self) -> None:
        self._sync_tool_paths()
        path, _ = QFileDialog.getSaveFileName(
            self,
            "导出文件",
            "score.pdf",
            "PDF (*.pdf);;PNG (*.png);;MIDI (*.mid);;All files (*.*)",
        )
        if path:
            self.vm.export_musicxml(Path(path))

    # ------------------------------------------------------------------
    # Image display
    # ------------------------------------------------------------------

    def _display_score_image(self, path: str) -> None:
        file_path = Path(path)
        ext = file_path.suffix.lower()
        if ext == ".pdf":
            self.score_image_label.setText(
                f"PDF 文件\n{file_path.name}\n（PDF 预览暂不支持）"
            )
            return
        if ext not in (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".gif"):
            self.score_image_label.setText(f"文件已选择\n{file_path.name}")
            return
        pixmap = QPixmap(str(file_path))
        if pixmap.isNull():
            self.score_image_label.setText(f"无法加载图片\n{file_path.name}")
            return
        self._score_pixmap = pixmap
        self._fit_score_image()

    def _fit_score_image(self) -> None:
        if not hasattr(self, "_score_pixmap") or self._score_pixmap.isNull():
            return
        label_size = self.score_image_label.size()
        if label_size.width() < 50 or label_size.height() < 50:
            label_size = QSize(500, 600)
        scaled = self._score_pixmap.scaled(
            label_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.score_image_label.setPixmap(scaled)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_score_pixmap"):
            self._fit_score_image()

    # ------------------------------------------------------------------
    # Jianpu sync helpers
    # ------------------------------------------------------------------

    def _on_omr_jianpu_changed(self) -> None:
        if self._syncing_jianpu:
            return
        self._syncing_jianpu = True
        text = self.omr_jianpu_edit.toPlainText()
        self.vm.set_jianpu_text(text)
        if self.jianpu_edit.toPlainText() != text:
            self.jianpu_edit.setPlainText(text)
        self._syncing_jianpu = False

    def _on_jianpu_tab_changed(self) -> None:
        if self._syncing_jianpu:
            return
        self._syncing_jianpu = True
        text = self.jianpu_edit.toPlainText()
        self.vm.set_jianpu_text(text)
        if self.omr_jianpu_edit.toPlainText() != text:
            self.omr_jianpu_edit.setPlainText(text)
        self._syncing_jianpu = False

    def _set_jianpu_preview(self, text: str) -> None:
        if self._syncing_jianpu:
            return
        self._syncing_jianpu = True
        if self.jianpu_edit.toPlainText() != text:
            self.jianpu_edit.setPlainText(text)
        if self.omr_jianpu_edit.toPlainText() != text:
            self.omr_jianpu_edit.setPlainText(text)
        self._syncing_jianpu = False

    def _on_input_file_changed(self, path: str) -> None:
        self.input_label.setText(path)
        self._display_score_image(path)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _sync_tool_paths(self) -> None:
        self.vm.set_tool_paths(
            self.audiveris_edit.text(),
            self.musescore_edit.text(),
            self.java_home_edit.text(),
        )

    def _warn(self, message: str) -> None:
        QMessageBox.warning(self, "Score Trans", message)

    def _set_busy(self, busy: bool) -> None:
        self.setEnabled(not busy)


def run_app() -> int:
    app = QApplication([])
    window = MainWindow()
    window.show()
    return app.exec()
