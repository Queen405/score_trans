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


@pytest.mark.skipif(sys.platform != "win32", reason="Windows installer process cleanup")
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

    def kill(args: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        calls.append(args)
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(installer.subprocess, "run", kill)
    with pytest.raises(subprocess.TimeoutExpired):
        installer.run_bounded("installer", 1)
    assert calls == [["taskkill", "/PID", "1234", "/T", "/F"]]


def test_successful_process_still_requires_installed_executable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(installer, "run_bounded", lambda *_, **__: None)
    with pytest.raises(RuntimeError, match="did not create"):
        installer._run_installer("installer", tmp_path)
    (tmp_path / "Score Trans.exe").write_bytes(b"installed")
    installer._run_installer("installer", tmp_path)


@pytest.fixture(autouse=True)
def isolated_reports(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(installer, "_REPORTS", tmp_path / "reports")


@pytest.mark.skipif(sys.platform != "win32", reason="Windows installer process cleanup")
def test_timeout_captures_diagnostics_before_killing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = []
    failure = subprocess.TimeoutExpired("installer", 1)

    class Child:
        pid = 1234

        def wait(self, timeout: float) -> int:
            if not calls:
                raise failure
            return 1

    class Diagnostic:
        pid = 5678

        def wait(self, timeout: float) -> int:
            assert timeout == 10
            return 0

    def popen(command: str | list[str], **kwargs: object) -> Child | Diagnostic:
        if isinstance(command, str):
            return Child()
        calls.append(command)
        kwargs["stdout"].write('{"window": "解压失败"}'.encode("utf-8"))
        return Diagnostic()

    monkeypatch.setattr(installer.subprocess, "Popen", popen)

    def run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        calls.append(args)
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(installer.subprocess, "run", run)
    clock = iter([0, 0, 2, 2, 2, 2, 2, 2])
    monkeypatch.setattr(installer.time, "monotonic", lambda: next(clock, 2))
    with pytest.raises(subprocess.TimeoutExpired):
        installer.run_bounded("installer", 1, install=tmp_path, phase="install")
    assert calls[0][0] == sys.executable
    assert "--windows" in calls[0]
    assert calls[1] == ["taskkill", "/PID", "1234", "/T", "/F"]
    report = (tmp_path / "reports/install.jsonl").read_text("utf-8")
    assert "解压失败" in report
    assert "timeout" in report


@pytest.mark.parametrize(
    "diagnostic_error",
    [
        OSError("unavailable"),
        subprocess.TimeoutExpired("diagnostic", 10),
    ],
)
@pytest.mark.skipif(sys.platform != "win32", reason="Windows installer process cleanup")
def test_diagnostic_and_cleanup_failure_preserve_original_timeout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    diagnostic_error: Exception,
) -> None:
    calls = []
    original = subprocess.TimeoutExpired("installer", 1)

    class Child:
        pid = 1234

        def wait(self, timeout: float) -> int:
            raise original

    class Diagnostic:
        pid = 5678

        def wait(self, timeout: float) -> int:
            raise diagnostic_error

    def popen(command: str | list[str], **kwargs: object) -> Child | Diagnostic:
        if isinstance(command, str):
            return Child()
        kwargs["stdout"].write(b"partial snapshot")
        return Diagnostic()

    monkeypatch.setattr(installer.subprocess, "Popen", popen)

    def run(args: list[str], **kwargs: object) -> None:
        calls.append(args)
        raise OSError("cleanup unavailable")

    monkeypatch.setattr(installer.subprocess, "run", run)
    clock = iter([0, 0, 2])
    monkeypatch.setattr(installer.time, "monotonic", lambda: next(clock, 2))
    with pytest.raises(subprocess.TimeoutExpired) as caught:
        installer.run_bounded("installer", 1, install=tmp_path)
    assert caught.value.cmd == original.cmd
    assert caught.value.timeout == original.timeout
    assert calls[-1] == ["taskkill", "/PID", "1234", "/T", "/F"]
    report = (tmp_path / "reports/install.jsonl").read_text("utf-8")
    assert "diagnostic-error" in report
    assert "cleanup-error" in report
    if isinstance(diagnostic_error, subprocess.TimeoutExpired):
        assert "partial snapshot" in report


def test_periodic_snapshots_keep_original_deadline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    waits = []
    now = 0.0

    class Child:
        pid = 1234

        def wait(self, timeout: float) -> int:
            nonlocal now
            waits.append(timeout)
            if len(waits) == 1:
                now += timeout
                raise subprocess.TimeoutExpired("installer", timeout)
            return 0

    monkeypatch.setattr(installer.subprocess, "Popen", lambda _: Child())
    monkeypatch.setattr(installer.time, "monotonic", lambda: now)
    calls = []

    def snapshot(*args: object, **kwargs: object) -> None:
        nonlocal now
        calls.append(kwargs)
        now += 5

    monkeypatch.setattr(installer, "_collect_diagnostics", snapshot)
    installer.run_bounded("installer", 40, install=tmp_path)
    assert waits == [30, 5]
    assert len(calls) == 1
    assert calls[0]["windows"] is False


@pytest.mark.skipif(
    sys.platform != "win32", reason="Windows venv launcher process tree"
)
def test_real_diagnostic_timeout_keeps_output_and_terminates_helper(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import ctypes
    import json
    from ctypes import wintypes

    tools = tmp_path / "tools"
    tools.mkdir()
    (tools / "installer_diagnostics.py").write_text(
        "import os, threading\nprint(os.getpid(), flush=True)\nthreading.Event().wait()\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(installer, "ROOT", tmp_path)
    installer._collect_diagnostics(1234, tmp_path, "install", windows=True, timeout=2)
    records = [
        json.loads(line)
        for line in (tmp_path / "reports/install.jsonl").read_text("utf-8").splitlines()
    ]
    failure = next(
        record for record in records if record["event"] == "diagnostic-error"
    )
    helper_pid = int(failure["output"].strip())
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.GetExitCodeProcess.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.DWORD),
    ]
    kernel.GetExitCodeProcess.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    handle = kernel.OpenProcess(0x1000, False, helper_pid)
    if handle:
        try:
            code = wintypes.DWORD()
            assert kernel.GetExitCodeProcess(handle, ctypes.byref(code))
            assert code.value != 259, "Diagnostic helper survived its timeout"
        finally:
            kernel.CloseHandle(handle)


@pytest.mark.parametrize("code", [2, 0xC0000005])
def test_nonzero_exit_is_recorded_and_propagated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, code: int
) -> None:
    import json

    class Child:
        pid = 1234

        def wait(self, timeout: float) -> int:
            return code

    monkeypatch.setattr(installer.subprocess, "Popen", lambda _: Child())
    with pytest.raises(subprocess.CalledProcessError) as caught:
        installer.run_bounded("installer", 600)
    assert caught.value.returncode == code
    records = [
        json.loads(line)
        for line in (tmp_path / "reports/install.jsonl").read_text("utf-8").splitlines()
    ]
    assert records[-1]["event"] == "exited"
    assert records[-1]["returncode"] == code


def test_unwritable_report_does_not_prevent_timeout_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    blocked = tmp_path / "not-a-directory"
    blocked.write_text("blocked", encoding="utf-8")
    monkeypatch.setattr(installer, "_REPORTS", blocked)
    calls = []

    class Child:
        pid = 1234

        def wait(self, timeout: float) -> int:
            raise subprocess.TimeoutExpired("installer", 1)

    monkeypatch.setattr(installer.subprocess, "Popen", lambda _: Child())
    monkeypatch.setattr(
        installer, "_terminate_tree", lambda child, phase: calls.append(child.pid)
    )
    with pytest.raises(subprocess.TimeoutExpired):
        installer.run_bounded("installer", 1)
    assert calls == [1234]


def test_desktop_smoke_passes_the_running_python_to_native_process_query(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = []
    monkeypatch.setattr(
        installer.subprocess, "run", lambda args, **kwargs: calls.append((args, kwargs))
    )
    executable = tmp_path / "Score Trans.exe"
    installer.desktop_smoke(executable, "installed")
    args, kwargs = calls[0]
    assert args[args.index("--python") + 1] == sys.executable
    assert args[args.index("--executable") + 1] == str(executable)
    assert kwargs["check"] is True
    assert kwargs["timeout"] == 130


@pytest.mark.parametrize(
    "code,crash", [(2, False), (0xC0000005, True), (0xC0000409, True)]
)
def test_crash_exit_requests_event_log_without_hiding_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, code: int, crash: bool
) -> None:
    calls = []

    class Child:
        pid = 2272

        def wait(self, timeout: float) -> int:
            return code

    monkeypatch.setattr(installer.subprocess, "Popen", lambda _: Child())
    monkeypatch.setattr(
        installer, "_collect_diagnostics", lambda *args, **kwargs: calls.append(kwargs)
    )
    with pytest.raises(subprocess.CalledProcessError) as caught:
        installer.run_bounded("installer", 600, install=tmp_path)
    assert caught.value.returncode == code
    assert calls == [{"windows": True, "crash": crash}]
