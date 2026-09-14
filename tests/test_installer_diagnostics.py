from __future__ import annotations

import ctypes
import importlib.util
import json
import os
import subprocess
import sys
from ctypes import wintypes
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "installer_diagnostics",
    Path(__file__).parents[1] / "tools/installer_diagnostics.py",
)
assert SPEC and SPEC.loader
diagnostics = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(diagnostics)


def test_directory_snapshot_tracks_partial_installation(tmp_path: Path) -> None:
    install = tmp_path / "安装目录"
    install.mkdir()
    for index in range(12):
        path = install / f"file-{index}.bin"
        path.write_bytes(b"x" * (index + 1))
        os.utime(path, (1_700_000_000 + index, 1_700_000_000 + index))
    snapshot = diagnostics.directory_snapshot(install)
    assert snapshot["file_count"] == 12
    assert snapshot["total_bytes"] == 78
    assert len(snapshot["recent_files"]) == 10
    assert snapshot["recent_files"][0]["path"] == "file-11.bin"
    assert snapshot["errors"] == []
    (install / "file-11.bin").unlink()
    assert diagnostics.directory_snapshot(install)["total_bytes"] == 66
    assert diagnostics.directory_snapshot(tmp_path / "missing")["exists"] is False


@pytest.mark.skipif(sys.platform != "win32", reason="Windows process snapshot API")
def test_process_tree_finds_owned_child_without_unrelated_processes() -> None:
    with subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import sys; print('ready', flush=True); sys.stdin.read()",
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
    ) as child:
        try:
            assert child.stdout.readline().strip() == "ready"
            tree = diagnostics.process_tree(os.getpid())
            by_pid = {entry["pid"]: entry for entry in tree}
            assert by_pid[child.pid]["parent_pid"] == os.getpid()
            assert os.getpid() in by_pid
            assert os.getppid() not in by_pid
            child_tree = diagnostics.process_tree(child.pid)
            child_pids = {entry["pid"] for entry in child_tree}
            assert child.pid in child_pids
            assert os.getpid() not in child_pids
            assert all(
                entry["pid"] == child.pid or entry["parent_pid"] in child_pids
                for entry in child_tree
            )
        finally:
            child.communicate(timeout=5)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows window inspection API")
def test_hidden_dialog_and_child_text_are_collected_with_unicode(
    capsys: pytest.CaptureFixture[str],
) -> None:
    user = ctypes.WinDLL("user32", use_last_error=True)
    user.CreateWindowExW.argtypes = [
        wintypes.DWORD,
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.DWORD,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.HWND,
        wintypes.HMENU,
        wintypes.HINSTANCE,
        wintypes.LPVOID,
    ]
    user.CreateWindowExW.restype = wintypes.HWND
    user.DestroyWindow.argtypes = [wintypes.HWND]
    user.DestroyWindow.restype = wintypes.BOOL
    # No WS_VISIBLE: this fixture must never display a window on the user's desktop.
    window = user.CreateWindowExW(
        0, "STATIC", "安装器诊断", 0, 0, 0, 100, 100, None, None, None, None
    )
    assert window, ctypes.WinError(ctypes.get_last_error())
    try:
        control = user.CreateWindowExW(
            0,
            "STATIC",
            "解压失败：文件不可用",
            0x40000000,
            0,
            0,
            100,
            20,
            window,
            None,
            None,
            None,
        )
        assert control, ctypes.WinError(ctypes.get_last_error())
        diagnostics.emit_windows({os.getpid()})
        records = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
        found = {entry["window"]: entry for entry in records if "window" in entry}
        assert found[window]["text"] == "安装器诊断"
        assert found[control]["text"] == "解压失败：文件不可用"
        assert found[control]["parent_window"] == window
        assert found[window]["visible"] is False
        diagnostics.emit_windows(set())
        assert all(
            "window" not in json.loads(line)
            for line in capsys.readouterr().out.splitlines()
        )
    finally:
        user.DestroyWindow(window)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows native process query")
def test_process_query_cli_needs_no_install_directory() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(SPEC.origin),
            "--processes-only",
            "--pid",
            str(os.getpid()),
        ],
        check=True,
        capture_output=True,
        encoding="utf-8",
        timeout=10,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    record = json.loads(result.stdout)
    assert list(record) == ["processes"]
    assert any(row["pid"] == os.getpid() for row in record["processes"])


def test_process_query_does_not_turn_native_api_failure_into_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        sys, "argv", ["installer_diagnostics.py", "--processes-only", "--pid", "1234"]
    )
    monkeypatch.setattr(diagnostics.sys.stdout, "reconfigure", lambda **kwargs: None)

    def fail(pid: int) -> list[dict[str, object]]:
        raise OSError("snapshot denied")

    monkeypatch.setattr(diagnostics, "process_tree", fail)
    with pytest.raises(OSError, match="snapshot denied"):
        diagnostics.main()
