from __future__ import annotations

import json

from starlette.types import ASGIApp, Message, Receive, Scope, Send


UPLOAD_PATHS = frozenset(
    {
        "/export/pdf",
        "/files/upload",
        "/pipeline",
        "/recognize",
    }
)


class RequestBodyLimitMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        *,
        max_bytes: int,
        paths: set[str] | frozenset[str] = UPLOAD_PATHS,
    ) -> None:
        if max_bytes <= 0:
            raise ValueError("max_bytes must be greater than zero")
        self.app = app
        self.max_bytes = max_bytes
        self.paths = frozenset(paths)

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        if scope["type"] != "http" or scope.get("path") not in self.paths:
            await self.app(scope, receive, send)
            return

        content_length = _content_length(scope)
        if content_length is not None and content_length > self.max_bytes:
            await self._send_too_large(send)
            return

        received = 0
        limit_response_sent = False
        response_started = False
        exceeded = False

        async def limited_receive() -> Message:
            nonlocal exceeded, limit_response_sent, received
            if exceeded:
                return {"type": "http.disconnect"}
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    exceeded = True
                    if not response_started:
                        await self._send_too_large(send)
                        limit_response_sent = True
                    return {"type": "http.disconnect"}
            return message

        async def tracked_send(message: Message) -> None:
            nonlocal response_started
            if exceeded:
                return
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, tracked_send)
        except Exception:
            if not exceeded:
                raise
        if exceeded and not response_started and not limit_response_sent:
            await self._send_too_large(send)

    async def _send_too_large(self, send: Send) -> None:
        body = json.dumps(
            {
                "error": (f"请求体超过上传总大小上限 {self.max_bytes} bytes"),
                "stage": "upload",
            },
            ensure_ascii=False,
        ).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json; charset=utf-8"),
                    (b"content-length", str(len(body)).encode("ascii")),
                    (b"connection", b"close"),
                ],
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": body,
                "more_body": False,
            }
        )


def _content_length(scope: Scope) -> int | None:
    for name, value in scope.get("headers", []):
        if name.lower() != b"content-length":
            continue
        try:
            parsed = int(value)
        except ValueError:
            return None
        return max(parsed, 0)
    return None
