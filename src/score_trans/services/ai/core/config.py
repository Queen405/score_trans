from __future__ import annotations

import os

from score_trans.utils.env import load_project_env

# Ensure project .env is loaded before reading AI-related variables.
load_project_env()

AI_BASE_URL: str = os.getenv("SCORE_TRANS_AI_BASE_URL", "")
AI_MODEL: str = os.getenv("SCORE_TRANS_AI_MODEL", "")
AI_API_KEY: str = os.getenv("SCORE_TRANS_AI_API_KEY", "")
AI_TIMEOUT: float = float(os.getenv("SCORE_TRANS_AI_TIMEOUT") or "120.0")
AI_TEMPERATURE: float = float(os.getenv("SCORE_TRANS_AI_TEMPERATURE") or "0")
AI_SYSTEM_MSG: str = os.getenv("SCORE_TRANS_AI_SYSTEM_MSG", "")
