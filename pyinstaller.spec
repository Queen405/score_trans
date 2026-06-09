# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for Score Trans backend

import os
from pathlib import Path

block_cipher = None
backend_dir = os.path.join(SPECPATH, "backend")

a = Analysis(
    [os.path.join(SPECPATH, "pyinstaller_entry.py")],
    pathex=[backend_dir],
    binaries=[],
    datas=[
        (os.path.join(backend_dir, "score_trans", "config", "env.example"), os.path.join("score_trans", "config")),
    ],
    hiddenimports=[
        # FastAPI / Starlette internals not auto-detected
        "multipart.multipart",
        "score_trans",
        "score_trans.api",
        "score_trans.api.app",
        "score_trans.api.health",
        "score_trans.api.convert",
        "score_trans.api.recognize",
        "score_trans.api.render",
        "score_trans.api.pipeline",
        "score_trans.api.files",
        "score_trans.api.history",
        "score_trans.api.export",
        "score_trans.api.settings",
        "score_trans.api.tasks",
        "score_trans.api.ai",
        "score_trans.config",
        "score_trans.config.settings",
        "score_trans.dao",
        "score_trans.dao.settings",
        "score_trans.dao.settings.settings_dao",
        "score_trans.dao.tasks",
        "score_trans.dao.tasks.task_dao",
        "score_trans.dao.history",
        "score_trans.dao.history.history_dao",
        "score_trans.dao.ai",
        "score_trans.dao.ai.chat_dao",
        "score_trans.domain",
        "score_trans.exec",
        "score_trans.exec.tasks",
        "score_trans.exec.tasks.actions",
        "score_trans.models",
        "score_trans.models.common",
        "score_trans.models.common.errors",
        "score_trans.models.common.paths",
        "score_trans.models.common.schemas",
        "score_trans.models.settings",
        "score_trans.models.settings.config",
        "score_trans.models.settings.schemas",
        "score_trans.services",
        "score_trans.services.settings",
        "score_trans.services.settings.settings_service",
        "score_trans.services.recognize",
        "score_trans.services.recognize.audiveris_service",
        "score_trans.services.recognize.external_tools",
        "score_trans.services.recognize.image_preprocessing",
        "score_trans.services.render",
        "score_trans.services.files",
        "score_trans.services.files.upload_service",
        "score_trans.services.export",
        "score_trans.services.ai",
        "score_trans.services.history",
        "score_trans.utils",
        "score_trans.utils.env",
        # Uvicorn internals
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
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "scipy", "numpy.testing", "PIL"],
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
