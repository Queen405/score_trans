from __future__ import annotations

import os


# Unit and integration tests opt out explicitly. Authentication behavior is covered
# by tests/test_api_auth.py with an injected token, while production defaults remain
# fail-closed.
os.environ.setdefault("SCORE_TRANS_API_AUTH_DISABLED", "1")
