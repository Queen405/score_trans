from __future__ import annotations

import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    # PyInstaller 打包模式：.env 与 backend.exe 同目录
    CONFIG_DIR = Path(sys.executable).resolve().parent
else:
    CONFIG_DIR = Path(__file__).resolve().parent
