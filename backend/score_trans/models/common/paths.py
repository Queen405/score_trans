from __future__ import annotations

import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    # PyInstaller 打包模式：backend.exe 位于 <app>/resources/backend/
    # PROJECT_ROOT 指向 <app>/resources/，与开发模式的项目根目录等价
    PROJECT_ROOT = Path(sys.executable).resolve().parent.parent
else:
    PROJECT_ROOT = Path(__file__).resolve().parents[4]

