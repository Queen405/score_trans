"""PyInstaller entry point for Score Trans backend.

Bundles the FastAPI application into a standalone executable.
When frozen (PyInstaller), PROJECT_ROOT is set via paths.py to
<app>/resources/ so that .env, work/, and third_party/ all resolve
to the correct packaged locations.
"""

import multiprocessing
import sys

multiprocessing.freeze_support()

if __name__ == "__main__":
    host = "127.0.0.1"
    port = "19200"

    # Parse CLI args: --host / --port
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--host" and i + 1 < len(args):
            host = args[i + 1]
            i += 2
        elif args[i] == "--port" and i + 1 < len(args):
            port = args[i + 1]
            i += 2
        else:
            i += 1

    import uvicorn

    uvicorn.run(
        "score_trans.api.app:create_app",
        factory=True,
        host=host,
        port=int(port),
    )
