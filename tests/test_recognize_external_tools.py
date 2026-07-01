from __future__ import annotations

from pathlib import Path

from score_trans.models.settings.config import ToolConfig
from score_trans.services.recognize import external_tools
from score_trans.services.recognize.external_tools import (
    CommandResult,
    recognize_with_audiveris,
)


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
        "-constant,org.audiveris.omr.step.LoadStep.maxPixelCount=20000000,"
        f"-export,-score-trans-overlay,-output,{output_dir.resolve()},{source.resolve()}",
        "-PaudiverisMaxHeap=2g",
    ]
