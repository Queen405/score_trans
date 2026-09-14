"""Read-only installer snapshots, run in a separately bounded Python process."""

from __future__ import annotations

import argparse
import ctypes
import heapq
import json
import os
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from ctypes import wintypes
from pathlib import Path

_WEVTUTIL = Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32/wevtutil.exe"
_EVENT_NS = {"e": "http://schemas.microsoft.com/win/2004/08/events/event"}
_CRASH_FIELDS = (
    "AppName",
    "AppVersion",
    "ModuleName",
    "ModuleVersion",
    "ExceptionCode",
    "FaultingOffset",
    "ProcessId",
    "AppPath",
    "ModulePath",
)


def parse_crash_events(xml: str, pid: int) -> list[dict[str, str | None]]:
    """Select recent Application Error records for this PID without exporting other data."""
    matches: list[dict[str, str | None]] = []
    for event in ET.fromstring(xml).findall("e:Event", _EVENT_NS):
        data = {
            item.get("Name"): item.text or ""
            for item in event.findall("e:EventData/e:Data", _EVENT_NS)
        }
        value = data.get("ProcessId", "").strip()
        try:
            event_pid = int(value, 16 if value.lower().startswith("0x") else 10)
        except ValueError:
            continue
        if event_pid != pid:
            continue
        created = event.find("e:System/e:TimeCreated", _EVENT_NS)
        matches.append(
            {
                "timestamp": created.get("SystemTime") if created is not None else None,
                **{key: data[key] for key in _CRASH_FIELDS if key in data},
            }
        )
    return matches


def crash_events(pid: int) -> list[dict[str, str | None]]:
    command = [
        str(_WEVTUTIL),
        "qe",
        "Application",
        "/q:*[System[(EventID=1000) and TimeCreated[timediff(@SystemTime) <= 120000]]]",
        "/f:xml",
        "/e:Events",
        "/c:20",
        "/rd:true",
        "/uni:true",
    ]
    # Error Reporting may publish the fault record shortly after process exit.
    # Three two-second queries plus two half-second waits fit the collector budget.
    for attempt in range(3):
        result = subprocess.run(
            command,
            capture_output=True,
            timeout=2,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode:
            raw = result.stderr
            encoding = (
                "utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8"
            )
            raise RuntimeError(
                f"Windows crash event query failed ({result.returncode}): "
                f"{raw.decode(encoding, errors='replace').strip()}"
            )
        events = parse_crash_events(result.stdout.decode("utf-16"), pid)
        if events:
            return events
        if attempt < 2:
            time.sleep(0.5)
    return []


def emit(record: dict[str, object]) -> None:
    print(json.dumps(record, ensure_ascii=False), flush=True)


def directory_snapshot(install: Path) -> dict[str, object]:
    count = total = 0
    recent: list[tuple[int, str, int]] = []
    errors: list[str] = []

    def record_error(error: OSError) -> None:
        if len(errors) < 10:
            errors.append(str(error))

    for root, directories, files in os.walk(install, onerror=record_error):
        directories[:] = [
            name
            for name in directories
            if not (Path(root) / name).is_symlink()
            and not (Path(root) / name).is_junction()
        ]
        for name in files:
            path = Path(root) / name
            try:
                if path.is_symlink():
                    continue
                stat = path.stat()
            except OSError as error:
                record_error(error)
                continue
            count += 1
            total += stat.st_size
            heapq.heappush(
                recent, (stat.st_mtime_ns, str(path.relative_to(install)), stat.st_size)
            )
            if len(recent) > 10:
                heapq.heappop(recent)
    return {
        "directory": str(install),
        "exists": install.exists(),
        "file_count": count,
        "total_bytes": total,
        "recent_files": [
            {"path": path, "size": size, "mtime_ns": mtime}
            for mtime, path, size in sorted(recent, reverse=True)
        ],
        "errors": errors,
    }


def process_tree(pid: int) -> list[dict[str, object]]:
    class ProcessEntry(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.c_size_t),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", wintypes.LONG),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", wintypes.WCHAR * 260),
        ]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    for name in ("Process32FirstW", "Process32NextW"):
        function = getattr(kernel, name)
        function.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry)]
        function.restype = wintypes.BOOL
    snapshot = kernel.CreateToolhelp32Snapshot(0x00000002, 0)  # TH32CS_SNAPPROCESS
    if snapshot == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    entries: list[dict[str, object]] = []
    try:
        entry = ProcessEntry()
        entry.dwSize = ctypes.sizeof(entry)
        found = kernel.Process32FirstW(snapshot, ctypes.byref(entry))
        while found:
            entries.append(
                {
                    "pid": entry.th32ProcessID,
                    "parent_pid": entry.th32ParentProcessID,
                    "name": entry.szExeFile,
                    "threads": entry.cntThreads,
                }
            )
            found = kernel.Process32NextW(snapshot, ctypes.byref(entry))
        if ctypes.get_last_error() != 18:  # ERROR_NO_MORE_FILES
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        kernel.CloseHandle(snapshot)
    owned = {pid}
    while True:
        children = {entry["pid"] for entry in entries if entry["parent_pid"] in owned}
        if children <= owned:
            break
        owned.update(children)
    return [entry for entry in entries if entry["pid"] in owned]


def emit_windows(pids: set[int]) -> None:
    user = ctypes.WinDLL("user32", use_last_error=True)
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    user.EnumWindows.restype = wintypes.BOOL
    user.EnumChildWindows.argtypes = [wintypes.HWND, callback_type, wintypes.LPARAM]
    user.EnumChildWindows.restype = wintypes.BOOL
    user.GetWindowThreadProcessId.argtypes = [
        wintypes.HWND,
        ctypes.POINTER(wintypes.DWORD),
    ]
    user.GetWindowThreadProcessId.restype = wintypes.DWORD
    user.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user.GetClassNameW.restype = ctypes.c_int
    user.IsWindowVisible.argtypes = [wintypes.HWND]
    user.IsWindowVisible.restype = wintypes.BOOL
    user.SendMessageTimeoutW.argtypes = [
        wintypes.HWND,
        wintypes.UINT,
        ctypes.c_size_t,
        ctypes.c_ssize_t,
        wintypes.UINT,
        wintypes.UINT,
        ctypes.POINTER(ctypes.c_size_t),
    ]
    user.SendMessageTimeoutW.restype = ctypes.c_ssize_t
    inspected = 0

    def describe(hwnd: int, parent: int) -> bool:
        nonlocal inspected
        if inspected >= 100:
            return False
        owner = wintypes.DWORD()
        user.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value not in pids:
            return True
        inspected += 1
        text = ctypes.create_unicode_buffer(2048)
        name = ctypes.create_unicode_buffer(256)
        result = ctypes.c_size_t()
        user.GetClassNameW(hwnd, name, len(name))
        # WM_GETTEXT with SMTO_BLOCK | SMTO_ABORTIFHUNG; never wait on a stuck UI.
        readable = user.SendMessageTimeoutW(
            hwnd,
            0x000D,
            len(text),
            ctypes.addressof(text),
            0x0003,
            100,
            ctypes.byref(result),
        )
        emit(
            {
                "window": hwnd,
                "parent_window": parent,
                "pid": owner.value,
                "class": name.value,
                "visible": bool(user.IsWindowVisible(hwnd)),
                "text": text.value if readable else "",
                "text_readable": bool(readable),
            }
        )
        return True

    @callback_type
    def child_window(hwnd: int, parent: int) -> bool:
        return describe(hwnd, parent)

    @callback_type
    def top_window(hwnd: int, unused: int) -> bool:
        owner = wintypes.DWORD()
        user.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value in pids:
            if not describe(hwnd, 0):
                return False
            user.EnumChildWindows(hwnd, child_window, hwnd)
        return True

    user.EnumWindows(top_window, 0)
    emit({"windows_inspected": inspected, "window_limit_reached": inspected >= 100})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install", type=Path)
    parser.add_argument("--pid", required=True, type=int)
    parser.add_argument("--windows", action="store_true")
    parser.add_argument("--processes-only", action="store_true")
    parser.add_argument("--crash-events", action="store_true")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    if args.pid <= 0:
        parser.error("--pid must be positive")
    if args.processes_only:
        # Strict machine-readable query for desktop smoke: API failures must fail CI.
        emit({"processes": process_tree(args.pid)})
        return
    if args.install is None:
        parser.error("--install is required unless --processes-only is set")
    if args.windows:
        # Emit each result immediately so the parent can preserve partial output.
        try:
            processes = process_tree(args.pid)
            emit({"processes": processes})
            emit_windows({int(entry["pid"]) for entry in processes})
        except Exception as error:
            emit({"process_snapshot_error": str(error)})
    emit(directory_snapshot(args.install))
    if args.crash_events:
        try:
            emit({"crash_events": crash_events(args.pid)})
        except Exception as error:
            emit({"crash_event_error": str(error)})


if __name__ == "__main__":
    main()
