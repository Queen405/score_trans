"""PyInstaller entry point for the Score Trans backend.

Launches the FastAPI app via uvicorn. Accepts ``--host`` / ``--port`` so the
Electron main process can spawn the packaged binary the same way on Windows
(``backend.exe``) and macOS (``backend``).

Environment variables (``SCORE_TRANS_API_TOKEN`` etc.) must be present in the
process environment before this module is imported, because
``score_trans.config.settings`` reads them at import time. Electron injects
them when spawning; ``load_project_env()`` also loads ``.env`` from the
directory next to this executable (``CONFIG_DIR``).
"""

from __future__ import annotations

import argparse

import uvicorn

from score_trans.api.app import create_app


def main() -> None:
    parser = argparse.ArgumentParser(prog="backend", description="Score Trans backend")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host")
    parser.add_argument("--port", type=int, default=19200, help="Bind port")
    args = parser.parse_args()

    uvicorn.run(
        create_app,
        host=args.host,
        port=args.port,
        factory=True,
        log_level="info",
    )


if __name__ == "__main__":
    main()
