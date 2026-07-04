from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile

from score_trans.domain.parse.musicxml import read_musicxml_text
from score_trans.models.settings.config import ToolConfig
from score_trans.services.recognize import external_tools
from score_trans.services.recognize.external_tools import (
    CommandResult,
    recognize_with_audiveris,
)


def _write_mxl(path: Path, measure_numbers: list[int]) -> None:
    measures = "".join(
        f'<measure number="{number}"><note><rest/><duration>1</duration></note></measure>'
        for number in measure_numbers
    )
    score = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<score-partwise version="4.0">'
        '<part-list><score-part id="P1"><part-name>Music</part-name></score-part></part-list>'
        f'<part id="P1">{measures}</part>'
        "</score-partwise>"
    )
    container = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<container version="1.0" '
        'xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
        "<rootfiles>"
        '<rootfile full-path="score.xml" '
        'media-type="application/vnd.recordare.musicxml+xml"/>'
        "</rootfiles>"
        "</container>"
    )
    with ZipFile(path, "w") as archive:
        archive.writestr("META-INF/container.xml", container)
        archive.writestr("score.xml", score)


def test_recognize_with_audiveris_passes_original_input(
    monkeypatch, tmp_path: Path
) -> None:
    source = tmp_path / "scan.pdf"
    output_dir = tmp_path / "omr"
    source.write_bytes(b"%PDF-1.4")
    calls: list[list[str]] = []

    def fake_run(args, cwd=None, env=None) -> CommandResult:
        calls.append(args)
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "scan.musicxml").write_text("<score-partwise/>", encoding="utf-8")
        return CommandResult(args=args, stdout="", stderr="")

    monkeypatch.setattr(external_tools, "_run", fake_run)

    result = recognize_with_audiveris(
        source,
        output_dir,
        ToolConfig(audiveris_path="audiveris"),
    )

    assert result.name == "scan.musicxml"
    assert calls
    assert calls[0][-1] == str(source.resolve())
    assert not (output_dir / "_preprocessed").exists()


def test_recognize_with_audiveris_enables_implicit_tuplets_by_default(
    monkeypatch, tmp_path: Path
) -> None:
    source = tmp_path / "scan.png"
    output_dir = tmp_path / "omr"
    source.write_bytes(b"png")
    calls: list[list[str]] = []

    def fake_run(args, cwd=None, env=None) -> CommandResult:
        calls.append(args)
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "scan.musicxml").write_text(
            "<score-partwise/>",
            encoding="utf-8",
        )
        return CommandResult(args=args, stdout="", stderr="")

    monkeypatch.setattr(external_tools, "_run", fake_run)

    recognize_with_audiveris(
        source,
        output_dir,
        ToolConfig(audiveris_path="audiveris"),
    )

    implicit_setting = "org.audiveris.omr.sheet.ProcessingSwitches.implicitTuplets=true"
    assert ["-constant", implicit_setting] == calls[0][
        calls[0].index(implicit_setting) - 1 : calls[0].index(implicit_setting) + 1
    ]


def test_configured_implicit_tuplets_override_is_preserved() -> None:
    setting_name = "org.audiveris.omr.sheet.ProcessingSwitches.implicitTuplets"
    constants = external_tools._merged_audiveris_constants(
        ToolConfig(audiveris_constants=f"{setting_name}=false")
    )

    assert f"{setting_name}=false" in constants
    assert f"{setting_name}=true" not in constants


def test_recognize_with_audiveris_merges_all_movements_in_order(
    monkeypatch, tmp_path: Path
) -> None:
    source = tmp_path / "scan.png"
    output_dir = tmp_path / "omr"
    source.write_bytes(b"png")

    def fake_run(args, cwd=None, env=None) -> CommandResult:
        output_dir.mkdir(parents=True, exist_ok=True)
        _write_mxl(output_dir / "scan.mvt2.mxl", [7, 8, 9])
        _write_mxl(output_dir / "scan.mvt1.mxl", [1, 2])
        return CommandResult(args=args, stdout="", stderr="")

    monkeypatch.setattr(external_tools, "_run", fake_run)

    result = recognize_with_audiveris(
        source,
        output_dir,
        ToolConfig(audiveris_path="audiveris"),
    )

    root = ET.fromstring(read_musicxml_text(result))
    measures = root.findall("./part/measure")
    assert result.name == "scan.musicxml"
    assert [measure.get("number") for measure in measures] == [
        "1",
        "2",
        "7",
        "8",
        "9",
    ]


def test_recognize_with_audiveris_applies_configured_java_omr_args(
    monkeypatch, tmp_path: Path
) -> None:
    source = tmp_path / "scan.png"
    output_dir = tmp_path / "omr"
    source.write_bytes(b"png")
    calls: list[list[str]] = []

    def fake_run(args, cwd=None, env=None) -> CommandResult:
        calls.append(args)
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "scan.musicxml").write_text("<score-partwise/>", encoding="utf-8")
        return CommandResult(args=args, stdout="", stderr="")

    monkeypatch.setattr(external_tools, "_run", fake_run)

    recognize_with_audiveris(
        source,
        output_dir,
        ToolConfig(
            audiveris_path="audiveris",
            audiveris_step="PAGE",
            audiveris_force=True,
            audiveris_save=True,
            audiveris_swap=True,
            audiveris_transcribe=True,
            audiveris_sheets="1 3-4",
            audiveris_constants="alpha=1;beta=two",
            audiveris_extra_args="-run org.example.CustomRunner",
        ),
    )

    assert calls[0] == [
        "audiveris",
        "-batch",
        "-step",
        "PAGE",
        "-force",
        "-save",
        "-swap",
        "-transcribe",
        "-sheets",
        "1 3-4",
        "-constant",
        "alpha=1",
        "-constant",
        "beta=two",
        "-constant",
        "org.audiveris.omr.sheet.ProcessingSwitches.implicitTuplets=true",
        "-constant",
        "org.audiveris.omr.step.LoadStep.maxPixelCount=20000000",
        "-run",
        "org.example.CustomRunner",
        "-export",
        "-score-trans-overlay",
        "-output",
        str(output_dir.resolve()),
        str(source.resolve()),
    ]


def test_recognize_with_gradle_uses_configured_java_omr_args(
    monkeypatch, tmp_path: Path
) -> None:
    source = tmp_path / "scan.png"
    output_dir = tmp_path / "omr"
    gradle = tmp_path / "gradlew.bat"
    source.write_bytes(b"png")
    calls: list[tuple[list[str], Path | None]] = []

    def fake_run(args, cwd=None, env=None) -> CommandResult:
        calls.append((args, cwd))
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "scan.musicxml").write_text("<score-partwise/>", encoding="utf-8")
        return CommandResult(args=args, stdout="", stderr="")

    monkeypatch.setattr(external_tools, "_run", fake_run)

    recognize_with_audiveris(
        source,
        output_dir,
        ToolConfig(
            audiveris_path=str(gradle),
            audiveris_step="PAGE",
            audiveris_constants="alpha=1",
        ),
    )

    args, cwd = calls[0]
    assert cwd == gradle.parent
    assert args == [
        str(gradle),
        ":app:run",
        "-PcmdLineArgs="
        "-batch,-step,PAGE,-save,-constant,alpha=1,"
        "-constant,"
        "org.audiveris.omr.sheet.ProcessingSwitches.implicitTuplets=true,"
        "-constant,org.audiveris.omr.step.LoadStep.maxPixelCount=20000000,"
        f"-export,-score-trans-overlay,-output,{output_dir.resolve()},{source.resolve()}",
        "-PaudiverisMaxHeap=2g",
    ]
