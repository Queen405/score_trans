# PyInstaller spec for the Score Trans backend.
#
# Produces a one-folder bundle ``dist/backend/`` containing the executable
# (``backend.exe`` on Windows, ``backend`` elsewhere) plus ``_internal/`` with
# the Python runtime, dependencies, and package data (fonts, ai_prompt.yaml,
# published_defaults.json, env.example).
#
# Run:
#   python -m PyInstaller pyinstaller.spec --noconfirm
#
# The executable's sibling directory (``CONFIG_DIR`` in paths.py) is where the
# build flow additionally copies ``.env`` and ``published_defaults.json`` so
# they are discoverable next to the binary at runtime.

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files

# SPECPATH is the directory containing this spec file (project root).
project_root = Path(SPECPATH)
backend_root = project_root / "backend"

datas = collect_data_files("score_trans")

# Uvicorn selects protocol implementations dynamically via string imports; pin
# the common ones so PyInstaller does not tree-shake them out.
hiddenimports = [
    "uvicorn.logging",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.protocols.websockets.websockets_impl",
    "uvicorn.protocols.websockets.wsproto_impl",
    "uvicorn.lifespan.on",
]

a = Analysis(
    [str(project_root / "pyinstaller_entry.py")],
    pathex=[str(backend_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="backend",
)
