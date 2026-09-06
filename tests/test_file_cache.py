from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from score_trans.api.app import create_app
from score_trans.api.dependencies import get_file_actions
from score_trans.exec.files.actions import FileActions
from score_trans.models.settings.config import ToolConfig
from score_trans.services.files.upload_service import UploadService


@pytest.mark.parametrize("origin", [None, "http://localhost:5173", "null"])
@pytest.mark.parametrize("method", ["GET", "HEAD", "RANGE"])
def test_file_responses_are_not_cached_across_origins_or_sessions(
    tmp_path: Path, origin: str | None, method: str
) -> None:
    uploads = UploadService(ToolConfig(work_dir=tmp_path / "work"))
    source = tmp_path / "page.png"
    source.write_bytes(b"score-image")
    file_id = uploads.register(source)
    token = "file-cache-test-token-at-least-32-characters"
    app = create_app(api_token=token, auth_disabled=False)
    app.dependency_overrides[get_file_actions] = lambda: FileActions(uploads)
    headers = {"Authorization": f"Bearer {token}"}
    if origin is not None:
        headers["Origin"] = origin
    if method == "RANGE":
        headers["Range"] = "bytes=0-0"
    response = TestClient(app).request(
        "GET" if method == "RANGE" else method,
        f"/files/{file_id}",
        headers=headers,
    )

    assert response.status_code == (206 if method == "RANGE" else 200)
    assert "no-store" in response.headers.get("cache-control", "")
    if origin is not None:
        assert response.headers["access-control-allow-origin"] == origin
    if method == "GET":
        assert response.content == b"score-image"
    elif method == "HEAD":
        assert response.content == b""
    else:
        assert response.content == b"s"
