from __future__ import annotations

from fastapi import Request
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient

from score_trans.api.app import create_app


TEST_TOKEN = "score-trans-test-token-32-bytes-long"
AUTH_HEADERS = {"Authorization": f"Bearer {TEST_TOKEN}"}


def _authenticated_app():
    app = create_app(api_token=TEST_TOKEN, auth_disabled=False)

    @app.api_route(
        "/_test/auth-transport",
        methods=["GET", "POST", "HEAD"],
        include_in_schema=False,
    )
    async def auth_transport(request: Request):
        if request.method == "HEAD":
            return None
        return {
            "body_size": len(await request.body()),
            "range": request.headers.get("range"),
        }

    @app.get("/_test/auth-stream", include_in_schema=False)
    async def auth_stream():
        async def events():
            yield 'data: {"status":"ok"}\n\n'

        return StreamingResponse(events(), media_type="text/event-stream")

    return app


def test_protected_routes_reject_missing_malformed_and_wrong_tokens() -> None:
    client = TestClient(_authenticated_app())

    for headers in (
        {},
        {"Authorization": TEST_TOKEN},
        {"Authorization": "Basic abc"},
        {"Authorization": "Bearer wrong-token"},
    ):
        response = client.get("/settings", headers=headers)
        assert response.status_code == 401
        assert response.json() == {"error": "未授权", "stage": "auth"}
        assert response.headers["www-authenticate"] == "Bearer"
        assert TEST_TOKEN not in response.text
        assert TEST_TOKEN not in repr(response.headers)


def test_health_and_cors_preflight_remain_available_without_credentials() -> None:
    client = TestClient(_authenticated_app())

    assert client.get("/health").status_code == 200
    preflight = client.options(
        "/settings",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )

    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == (
        "http://127.0.0.1:5173"
    )


def test_bearer_auth_covers_json_body_head_range_openapi_and_sse() -> None:
    client = TestClient(_authenticated_app())

    body_response = client.post(
        "/_test/auth-transport",
        content=b"multipart-like-body",
        headers=AUTH_HEADERS,
    )
    head_response = client.head("/_test/auth-transport", headers=AUTH_HEADERS)
    range_response = client.get(
        "/_test/auth-transport",
        headers={**AUTH_HEADERS, "Range": "bytes=0-0"},
    )

    assert body_response.status_code == 200
    assert body_response.json()["body_size"] == len(b"multipart-like-body")
    assert head_response.status_code == 200
    assert range_response.status_code == 200
    assert range_response.json()["range"] == "bytes=0-0"
    assert client.get("/openapi.json").status_code == 401
    assert client.get("/openapi.json", headers=AUTH_HEADERS).status_code == 200

    assert client.get("/_test/auth-stream").status_code == 401
    with client.stream("GET", "/_test/auth-stream", headers=AUTH_HEADERS) as response:
        assert response.status_code == 200
        assert '{"status":"ok"}' in "".join(response.iter_text())


def test_query_token_is_rejected_and_auth_can_only_be_explicitly_disabled() -> None:
    client = TestClient(_authenticated_app())

    assert client.get(f"/settings?token={TEST_TOKEN}").status_code == 401
    assert TestClient(create_app(auth_disabled=True)).get("/settings").status_code == 200


def test_enabled_auth_rejects_missing_or_short_token() -> None:
    for token in ("", "too-short"):
        try:
            create_app(api_token=token, auth_disabled=False)
        except ValueError as exc:
            assert "SCORE_TRANS_API_TOKEN" in str(exc)
            assert "32" in str(exc)
        else:
            raise AssertionError("enabled authentication accepted an unsafe token")
