from __future__ import annotations

import os
from pathlib import Path

from score_trans.utils.env import load_project_env

# Unit and integration tests opt out explicitly. Authentication behavior is covered
# by tests/test_api_auth.py with an injected token, while production defaults remain
# fail-closed.
os.environ.setdefault("SCORE_TRANS_API_AUTH_DISABLED", "1")

# CI 等无 .env 的环境用 env.example 兜底；本地 .env 由 settings.py 加载
# （load_project_env 默认 override=False，不覆盖已设变量，故本地 .env 仍优先生效）。
_env_file = Path(__file__).parents[1] / ".env"
if not _env_file.is_file():
    load_project_env(
        Path(__file__).parents[1] / "backend" / "score_trans" / "config" / "env.example"
    )
