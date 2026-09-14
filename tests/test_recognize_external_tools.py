from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile

import pytest

from score_trans.domain.parse.musicxml import read_musicxml_text
from score_trans.models.common.errors import ExternalToolError
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
        "org.audiveris.omr.step.LoadStep.maxPixelCount=4500000",
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
        "--no-daemon",
        ":app:run",
        (
            "-PcmdLineArgs="
            "-batch,-step,PAGE,-save,-constant,alpha=1,"
            "-constant,"
            "org.audiveris.omr.sheet.ProcessingSwitches.implicitTuplets=true,"
            "-constant,org.audiveris.omr.step.LoadStep.maxPixelCount=4500000,"
            f"-export,-score-trans-overlay,-output,{output_dir.resolve()},{source.resolve()}"
        ),
        "-PaudiverisMaxHeap=3g",
    ]


def test_recognize_with_gradle_retries_with_no_daemon(
    monkeypatch, tmp_path: Path
) -> None:
    source = tmp_path / "scan.png"
    retry_source = tmp_path / "retry.png"
    output_dir = tmp_path / "omr"
    gradle = tmp_path / "gradlew.bat"
    source.write_bytes(b"png")
    retry_source.write_bytes(b"upscaled png")
    calls: list[list[str]] = []

    def fake_run(args, cwd=None, env=None) -> CommandResult:
        calls.append(args)
        if len(calls) == 1:
            raise ExternalToolError(
                "Audiveris failed",
                stdout="too low interline value of 10 pixels",
            )
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "scan.musicxml").write_text("<score-partwise/>", encoding="utf-8")
        return CommandResult(args=args, stdout="", stderr="")

    monkeypatch.setattr(external_tools, "_run", fake_run)
    monkeypatch.setattr(
        external_tools,
        "_maybe_retry_after_low_interline",
        lambda error, input_file, output_dir, config: retry_source,
    )

    recognize_with_audiveris(
        source,
        output_dir,
        ToolConfig(audiveris_path=str(gradle)),
    )

    assert len(calls) == 2
    assert all(args[1:3] == ["--no-daemon", ":app:run"] for args in calls)


@pytest.mark.parametrize("fail", [False, True])
def test_bundled_jar_uses_utf8_argument_file_and_cleans_it_up(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, fail: bool
) -> None:
    jar = tmp_path / "安装 resources" / "lib" / "audiveris.jar"
    jar.parent.mkdir(parents=True)
    jar.touch()
    java_home = tmp_path / "jdk"
    java = java_home / "bin" / external_tools.java_binary_name()
    java.parent.mkdir(parents=True)
    java.touch()
    source = tmp_path / "乐谱, sample.png"
    output = tmp_path / "用户 smoke, path" / "output"
    config = ToolConfig(
        audiveris_path=str(jar),
        java_home=str(java_home),
        audiveris_max_heap="2g",
        audiveris_sheets="1 3-4",
        audiveris_extra_args='-run "org.example.CustomRunner"',
    )
    files: list[Path] = []
    failure = ExternalToolError("recognition failed")

    def fake_run(args: list[str], cwd: Path | None = None, env=None) -> CommandResult:
        assert args[0] == str(java)
        assert "-Xmx2g" in args
        assert "-Dfile.encoding=UTF-8" in args
        assert "--disable-@files" in args
        assert args.index("--disable-@files") < args.index("Audiveris")
        assert args[args.index("-cp") + 1] == str(jar.parent / "*")
        assert cwd == output
        application_args = args[args.index("Audiveris") + 1 :]
        assert len(application_args) == 1
        assert application_args[0].startswith("@")
        assert application_args[0].isascii()
        argfile = cwd / application_args[0][1:]
        files.append(argfile)
        restored = argfile.read_text(encoding="utf-8").splitlines()
        assert restored[-5:] == [
            "-export",
            "-score-trans-overlay",
            "-output",
            str(output),
            str(source),
        ]
        assert restored[restored.index("-sheets") + 1] == "1 3-4"
        assert restored[restored.index("-run") + 1] == "org.example.CustomRunner"
        if fail:
            raise failure
        return CommandResult(args=args, stdout="", stderr="")

    monkeypatch.setattr(external_tools, "_run", fake_run)
    if fail:
        with pytest.raises(ExternalToolError) as caught:
            external_tools._run_audiveris(source, output, config)
        assert caught.value is failure
    else:
        external_tools._run_audiveris(source, output, config)
    assert len(files) == 1
    assert not files[0].exists()
    assert not list(output.iterdir())


def test_bundled_jar_rejects_line_breaks_in_argument_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    jar = tmp_path / "audiveris.jar"
    jar.touch()
    monkeypatch.setattr(
        external_tools,
        "_run",
        lambda *args, **kwargs: pytest.fail("must reject before launching Java"),
    )
    with pytest.raises(ExternalToolError, match="换行"):
        external_tools._run_audiveris(
            tmp_path / "input.png",
            tmp_path / "output",
            ToolConfig(audiveris_path=str(jar), audiveris_sheets="1" + chr(10) + "2"),
        )


def test_packaged_settings_prefer_distribution_jar(tmp_path: Path, monkeypatch) -> None:
    from score_trans.services.settings import settings_service

    jar = tmp_path / "lib" / "audiveris.jar"
    jar.parent.mkdir()
    jar.touch()
    monkeypatch.setattr(settings_service, "AUDIVERIS_PATH", "")
    monkeypatch.setattr(settings_service, "_LOCAL_AUDIVERIS_DIR", tmp_path)
    assert settings_service._default_audiveris_path() == str(jar)


def test_bundled_jar_resolves_paths_before_changing_working_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    jar = tmp_path / "lib/audiveris.jar"
    jar.parent.mkdir()
    jar.touch()
    java = tmp_path / "jdk/bin" / external_tools.java_binary_name()
    java.parent.mkdir(parents=True)
    java.touch()

    def fake_run(args: list[str], cwd: Path | None = None, env=None) -> CommandResult:
        assert args[0] == str(java)
        assert args[args.index("-cp") + 1] == str(jar.parent / "*")
        assert cwd == tmp_path / "用户 output"
        parameters = (cwd / args[-1][1:]).read_text(encoding="utf-8").splitlines()
        assert parameters[-2:] == [str(cwd), str(tmp_path / "乐谱.png")]
        return CommandResult(args=args, stdout="", stderr="")

    monkeypatch.setattr(external_tools, "_run", fake_run)
    external_tools._run_audiveris(
        Path("乐谱.png"),
        Path("用户 output"),
        ToolConfig(audiveris_path="lib/audiveris.jar", java_home="jdk"),
    )
