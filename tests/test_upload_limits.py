from __future__ import annotations

import asyncio
from io import BytesIO
from pathlib import Path

import pytest
from fastapi import UploadFile
from fastapi.testclient import TestClient

from score_trans.api.app import create_app
from score_trans.api.dependencies import get_file_actions
from score_trans.api.request_limits import RequestBodyLimitMiddleware
from score_trans.exec.export.actions import ExportActions
from score_trans.exec.files.actions import FileActions
from score_trans.models.common.errors import UploadTooLargeError
from score_trans.models.settings.config import ToolConfig
from score_trans.services.files.upload_service import UploadService


def test_upload_service_accepts_exact_limit_and_rejects_next_byte(
    tmp_path: Path,
) -> None:
    uploads = UploadService(
        ToolConfig(work_dir=tmp_path),
        max_upload_bytes=4,
    )

    accepted_id = uploads.save(
        UploadFile(file=BytesIO(b"1234"), filename="accepted.bin")
    )
    accepted_path = uploads.get_path(accepted_id)

    assert accepted_path is not None
    assert accepted_path.read_bytes() == b"1234"

    with pytest.raises(UploadTooLargeError, match="4 bytes"):
        uploads.save(UploadFile(file=BytesIO(b"12345"), filename="large.bin"))

    upload_dirs = [child for child in uploads.base_dir.iterdir() if child.is_dir()]
    assert upload_dirs == [accepted_path.parent]


def test_upload_route_maps_file_limit_to_413_without_partial_file(
    tmp_path: Path,
) -> None:
    app = create_app(max_upload_request_bytes=1024 * 1024)
    uploads = UploadService(
        ToolConfig(work_dir=tmp_path),
        max_upload_bytes=4,
    )
    app.dependency_overrides[get_file_actions] = lambda: FileActions(uploads)

    response = TestClient(app).post(
        "/files/upload",
        files={"file": ("large.bin", b"12345", "application/octet-stream")},
    )

    assert response.status_code == 413
    assert response.json() == {
        "error": "文件 large.bin 超过上传大小上限 4 bytes",
        "stage": "upload",
    }
    assert not any(child.is_dir() for child in uploads.base_dir.iterdir())


def test_request_limit_rejects_content_length_before_route_runs() -> None:
    app = create_app(max_upload_request_bytes=128)

    response = TestClient(app).post(
        "/files/upload",
        files={"file": ("large.bin", b"x" * 256, "application/octet-stream")},
    )

    assert response.status_code == 413
    assert response.json() == {
        "error": "请求体超过上传总大小上限 128 bytes",
        "stage": "upload",
    }


def test_request_limit_counts_streamed_body_without_content_length() -> None:
    sent: list[dict] = []
    messages = iter(
        [
            {"type": "http.request", "body": b"123", "more_body": True},
            {"type": "http.request", "body": b"45", "more_body": False},
        ]
    )

    async def inner(scope, receive, send) -> None:
        while True:
            message = await receive()
            if not message.get("more_body", False):
                break

    async def receive() -> dict:
        return next(messages)

    async def send(message: dict) -> None:
        sent.append(message)

    middleware = RequestBodyLimitMiddleware(
        inner,
        max_bytes=4,
        paths={"/upload"},
    )
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/upload",
        "headers": [],
    }

    asyncio.run(middleware(scope, receive, send))

    assert sent[0]["status"] == 413


def test_fastapi_stack_returns_413_for_chunked_multipart_body() -> None:
    body = (
        b'--x\r\nContent-Disposition: form-data; name="file"; '
        b'filename="large.bin"\r\n'
        b"Content-Type: application/octet-stream\r\n\r\n" + b"x" * 64 + b"\r\n--x--\r\n"
    )
    limit = len(body) - 10
    messages = iter(
        [
            {
                "type": "http.request",
                "body": body[:100],
                "more_body": True,
            },
            {
                "type": "http.request",
                "body": body[100:],
                "more_body": False,
            },
        ]
    )
    sent: list[dict] = []

    async def receive() -> dict:
        return next(messages)

    async def send(message: dict) -> None:
        sent.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/files/upload",
        "raw_path": b"/files/upload",
        "query_string": b"",
        "root_path": "",
        "headers": [
            (b"content-type", b"multipart/form-data; boundary=x"),
        ],
        "client": ("127.0.0.1", 1),
        "server": ("test", 80),
        "state": {},
    }

    asyncio.run(create_app(max_upload_request_bytes=limit)(scope, receive, send))

    assert sent[0]["status"] == 413
    assert str(limit).encode("ascii") in sent[1]["body"]


def test_export_pdf_limits_each_file_and_total_request(tmp_path: Path) -> None:
    uploads = UploadService(ToolConfig(work_dir=tmp_path))
    actions = ExportActions(
        uploads=uploads,
        max_upload_file_bytes=8,
        max_upload_request_bytes=15,
    )

    with pytest.raises(UploadTooLargeError, match="large.png.*8 bytes"):
        asyncio.run(
            actions.export_pdf(
                [UploadFile(file=BytesIO(b"x" * 9), filename="large.png")]
            )
        )

    with pytest.raises(UploadTooLargeError, match="请求体.*15 bytes"):
        asyncio.run(
            actions.export_pdf(
                [
                    UploadFile(
                        file=BytesIO(b"\x89PNG\r\n\x1a\n"),
                        filename="page-1.png",
                    ),
                    UploadFile(
                        file=BytesIO(b"\x89PNG\r\n\x1a\n"),
                        filename="page-2.png",
                    ),
                ]
            )
        )

    assert not any(child.suffix == ".pdf" for child in uploads.base_dir.iterdir())
