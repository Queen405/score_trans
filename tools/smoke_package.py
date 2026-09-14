"""Exercise the frozen backend and bundled Java with isolated user directories.

Run against electron-builder's final resources directory, never a source backend.
Outbound proxy endpoints are deliberately unusable; local API calls bypass proxies.
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def make_score(path: Path) -> None:
    """Deterministic, locally authored two-system score using the bundled OFL font."""
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("RGB", (2500, 1600), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(
        str(ROOT / "backend/score_trans/assets/fonts/Bravura.otf"), 160
    )
    for top in (350, 850):
        for i in range(5):
            draw.line((180, top + i * 40, 2320, top + i * 40), fill="black", width=3)
        draw.text((205, top + 120), "\ue050", font=font, fill="black", anchor="ls")
        for x in (180, 1240, 2320):
            draw.line((x, top, x, top + 160), fill="black", width=3)
        for i, x in enumerate((470, 670, 870, 1070, 1470, 1670, 1870, 2070)):
            y = top + 140 - (i % 4) * 20
            draw.text((x, y), "\ue0a4", font=font, fill="black", anchor="ls")
            draw.line((x + 47, y - 5, x + 47, y - 140), fill="black", width=3)
    image.save(path)


def validate_resources(resources: Path) -> None:
    exe = "backend.exe" if sys.platform == "win32" else "backend"
    java = "java.exe" if sys.platform == "win32" else "java"
    required = [
        f"backend/{exe}",
        "backend/.env",
        "backend/published_defaults.json",
        "third_party/audiveris/lib/audiveris.jar",
        f"third_party/jre/jdk/bin/{java}",
    ]
    if sys.platform == "win32":
        required.extend(
            [
                "third_party/jre/jdk/bin/java.dll",
                "third_party/jre/jdk/bin/server/jvm.dll",
                "third_party/jre/jdk/lib/jvm.cfg",
            ]
        )
    for relative in required:
        if not (resources / relative).is_file():
            raise ValueError(f"Missing packaged resource: {relative}")
    jars = list((resources / "third_party/audiveris/lib").glob("*.jar"))
    if len(jars) < 10:
        raise ValueError("Audiveris runtime dependencies missing")
    for entry in (resources / "third_party").rglob("*"):
        if ".trash-" in entry.name or entry.name in {
            "gradle_home",
            "gradlew",
            "gradlew.bat",
            ".gradle",
        }:
            raise ValueError(f"Build-only resource included: {entry}")


def smoke(resources: Path) -> None:
    resources = resources.resolve()
    validate_resources(resources)

    def snapshot() -> dict:
        return {
            str(p.relative_to(resources)): (p.stat().st_size, p.stat().st_mtime_ns)
            for p in resources.rglob("*")
            if p.is_file()
        }

    original_resources = snapshot()
    with tempfile.TemporaryDirectory(prefix="score-trans-smoke-") as temporary:
        # The work directory uses non-ASCII + spaces + comma to exercise
        # Unicode path handling in the Python backend. Java's FileSystemView
        # (used by Audiveris WellKnowns) requires a valid Windows user profile,
        # so HOME/USERPROFILE point to a separate ASCII-safe directory.
        work = Path(temporary) / "用户 smoke, path"
        work.mkdir()
        java_home_dir = Path(temporary) / "java-home"
        java_home_dir.mkdir()
        token = secrets.token_urlsafe(32)
        env = {k: v for k, v in os.environ.items() if not k.startswith("SCORE_TRANS_")}
        env.update(
            {
                "SCORE_TRANS_DATA_DIR": str(work / "data"),
                "SCORE_TRANS_CACHE_DIR": str(work / "cache"),
                "SCORE_TRANS_API_TOKEN": token,
                "SCORE_TRANS_API_AUTH_DISABLED": "0",
                "HOME": str(java_home_dir),
                "USERPROFILE": str(java_home_dir),
                "APPDATA": str(work / "AppData"),
                "LOCALAPPDATA": str(work / "LocalAppData"),
                "XDG_CONFIG_HOME": str(work / "config"),
                "XDG_DATA_HOME": str(work / "data"),
                "XDG_CACHE_HOME": str(work / "cache"),
                "GRADLE_USER_HOME": str(work / "empty-gradle"),
                "HTTP_PROXY": "http://127.0.0.1:9",
                "HTTPS_PROXY": "http://127.0.0.1:9",
                "http_proxy": "http://127.0.0.1:9",
                "https_proxy": "http://127.0.0.1:9",
                "JAVA_TOOL_OPTIONS": "-Dhttp.proxyHost=127.0.0.1 -Dhttp.proxyPort=9 -Dhttps.proxyHost=127.0.0.1 -Dhttps.proxyPort=9",
            }
        )
        for key in (
            "APPDATA",
            "LOCALAPPDATA",
            "XDG_CONFIG_HOME",
            "XDG_DATA_HOME",
            "XDG_CACHE_HOME",
        ):
            Path(env[key]).mkdir(parents=True, exist_ok=True)
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

        def request(
            route: str,
            payload: dict | bytes | None = None,
            content_type: str = "application/json",
        ) -> bytes:
            body = (
                json.dumps(payload).encode() if isinstance(payload, dict) else payload
            )
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}{route}",
                data=body,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": content_type,
                },
            )
            with opener.open(req, timeout=60) as response:
                return response.read()

        exe = (
            resources
            / "backend"
            / ("backend.exe" if sys.platform == "win32" else "backend")
        )
        with (work / "backend.log").open("w+", encoding="utf-8") as log:
            child = subprocess.Popen(
                [str(exe), "--port", str(port)],
                cwd=work,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=sys.platform != "win32",
            )
            try:
                for _ in range(60):
                    if child.poll() is not None:
                        raise RuntimeError("Frozen backend exited before healthy")
                    try:
                        request("/health")
                        break
                    except OSError:
                        time.sleep(1)
                else:
                    raise RuntimeError("Frozen backend startup timed out")
                text = "1=C\n4/4\n1 2 3 4 | 5 6 7 1' |"
                rendered = json.loads(
                    request("/render/jianpu-text-svg", {"jianpu_text": text})
                )
                svg_id = rendered["svg_file_id"]
                assert b"<svg" in request(f"/files/{svg_id}")
                pdf = json.loads(
                    request("/export/rendered-pdf", {"svg_file_ids": [svg_id]})
                )
                assert request(f"/files/{pdf['file_id']}").startswith(b"%PDF")
                midi = json.loads(request("/export/midi-text", {"jianpu_text": text}))
                assert request(f"/files/{midi['file_id']}").startswith(b"MThd")
                score = work / "smoke.png"
                make_score(score)
                boundary = "score-trans-smoke-boundary"
                body = (
                    f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="smoke.png"\r\nContent-Type: image/png\r\n\r\n'.encode()
                    + score.read_bytes()
                    + f"\r\n--{boundary}--\r\n".encode()
                )
                task = json.loads(
                    request(
                        "/recognize", body, f"multipart/form-data; boundary={boundary}"
                    )
                )
                for _ in range(180):
                    result = json.loads(request(f"/tasks/{task['task_id']}"))
                    if result["status"] == "failed":
                        raise RuntimeError(f"Packaged recognition failed: {result}")
                    if result["status"] == "completed":
                        musicxml = result["result"]["musicxml_text"]
                        assert "<note" in musicxml, "Recognition returned no notes"
                        break
                    time.sleep(1)
                else:
                    raise RuntimeError("Packaged recognition timed out")
                assert not (work / "empty-gradle").exists(), (
                    "Recognition invoked Gradle"
                )
                if snapshot() != original_resources:
                    raise RuntimeError(
                        "Runtime modified the installed application resources"
                    )
                print("Packaged health, SVG, PDF, MIDI and Java recognition passed")
            finally:
                if child.poll() is None:
                    if sys.platform == "win32":
                        subprocess.run(
                            ["taskkill", "/PID", str(child.pid), "/T", "/F"],
                            capture_output=True,
                        )
                    else:
                        os.killpg(child.pid, signal.SIGTERM)
                    try:
                        child.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        child.kill()
                        child.wait()
                log.seek(0)
                print(log.read())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("resources", type=Path)
    smoke(parser.parse_args().resources)
