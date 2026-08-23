# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for Score Trans backend

import os
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

block_cipher = None
backend_dir = os.path.join(SPECPATH, "backend")

# 将 backend/ 加入 sys.path，让 collect_submodules 能找到 score_trans
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# 自动收集 score_trans 所有子模块
all_score_trans_modules = collect_submodules("score_trans")

hidden_imports = [
    # ---- Core third-party packages ----
    "fastapi",
    "starlette",
    "starlette.middleware",
    "starlette.middleware.cors",
    "starlette.routing",
    "starlette.responses",
    "starlette.requests",
    "starlette.staticfiles",
    "multipart",
    "multipart.multipart",
    "uvicorn",
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "httpx",
    "PIL",
    "PIL.Image",
    "PIL.ImageOps",
    "PIL.ImageFilter",
    "PIL.ImageEnhance",
    "PIL.ImageChops",
    "PIL.ImageStat",
    "pydantic",
    "pydantic.fields",
    "pydantic_core",
    "anyio",
    "anyio._backends",
    "anyio._backends._asyncio",
    "h11",
    "sniffio",
    "idna",
    "click",
    "yaml",
    "zstandard",
    "mido",
    "fitz",
    "fontTools",
    "fontTools.pens.svgPathPen",
    "fontTools.ttLib",
    "sqlite3",
] + all_score_trans_modules

a = Analysis(
    [os.path.join(SPECPATH, "pyinstaller_entry.py")],
    pathex=[backend_dir],
    binaries=[],
    datas=[
        (os.path.join(backend_dir, "score_trans", "config", "env.example"), os.path.join("score_trans", "config")),
        (os.path.join(backend_dir, "score_trans", "config", "ai_prompt.yaml"), os.path.join("score_trans", "config")),
        (os.path.join(backend_dir, "score_trans", "assets", "fonts"), os.path.join("score_trans", "assets", "fonts")),
        (os.path.join(SPECPATH, "THIRD_PARTY_NOTICES.md"), "."),
    ],
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "scipy", "numpy.testing"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,        # 保留 stdout/stderr 供 uvicorn 使用（Electron 启动时 windowsHide 会隐藏窗口）
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
    upx=True,
    upx_exclude=[],
    name="backend",
)
