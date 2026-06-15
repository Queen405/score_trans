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
        (output_dir / "scan.musicxml").write_text(
            "<score-partwise/>", encoding="utf-8"
        )
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
