from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
SPEC = importlib.util.spec_from_file_location(
    "smoke_installer", TOOLS / "smoke_installer.py"
)
assert SPEC and SPEC.loader
installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer)
sys.path.remove(str(TOOLS))


@pytest.mark.parametrize("code", [2, 0xC0000005])
def test_existing_application_never_hides_install_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    code: int,
) -> None:
    (tmp_path / "Score Trans.exe").write_bytes(b"old installation")

    def fail(*args: object, **kwargs: object) -> None:
        raise subprocess.CalledProcessError(code, "installer")

    monkeypatch.setattr(installer, "run_bounded", fail)
    with pytest.raises(subprocess.CalledProcessError):
        installer._run_installer('"installer.exe" /S', tmp_path)


def test_timeout_kills_only_the_started_process_tree(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []

    class Child:
        pid = 1234
        first = True

        def wait(self, timeout: int) -> int:
            if self.first:
                self.first = False
                raise subprocess.TimeoutExpired("installer", timeout)
            return 1

    monkeypatch.setattr(installer.subprocess, "Popen", lambda _: Child())
    monkeypatch.setattr(
        installer.subprocess, "run", lambda args, **_: calls.append(args)
    )
    with pytest.raises(subprocess.TimeoutExpired):
        installer.run_bounded("installer", 1)
    assert calls == [["taskkill", "/PID", "1234", "/T", "/F"]]


def test_successful_process_still_requires_installed_executable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(installer, "run_bounded", lambda *_: None)
    with pytest.raises(RuntimeError, match="did not create"):
        installer._run_installer("installer", tmp_path)
    (tmp_path / "Score Trans.exe").write_bytes(b"installed")
    installer._run_installer("installer", tmp_path)
