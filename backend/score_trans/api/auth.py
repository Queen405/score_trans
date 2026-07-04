from __future__ import annotations

import secrets

from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send


MIN_API_TOKEN_LENGTH = 32
UNAUTHENTICATED_PATHS = frozenset({"/health"})


def validate_api_token(token: str, *, disabled: bool) -> None:
    if disabled:
        return
    if len(token) < MIN_API_TOKEN_LENGTH:
        raise ValueError(
            "SCORE_TRANS_API_TOKEN must contain at least "
            f"{MIN_API_TOKEN_LENGTH} characters when API authentication is enabled"
        )


class BearerAuthMiddleware:
    """Authenticate local API requests without buffering request or response streams."""

    def __init__(self, app: ASGIApp, *, token: str, disabled: bool) -> None:
        validate_api_token(token, disabled=disabled)
        self.app = app
        self.token = token
        self.disabled = disabled

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        if self._is_allowed_without_token(scope):
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        authorization = headers.get("authorization", "")
        scheme, separator, candidate = authorization.partition(" ")
        authenticated = (
            bool(separator)
            and scheme.lower() == "bearer"
            and bool(candidate)
            and secrets.compare_digest(candidate, self.token)
        )
        if authenticated:
            await self.app(scope, receive, send)
            return

        response = JSONResponse(
            status_code=401,
            content={"error": "未授权", "stage": "auth"},
            headers={"WWW-Authenticate": "Bearer"},
        )
        await response(scope, receive, send)

    def _is_allowed_without_token(self, scope: Scope) -> bool:
        if self.disabled or scope["type"] != "http":
            return True
        if scope.get("path") in UNAUTHENTICATED_PATHS:
            return True
        if scope.get("method") != "OPTIONS":
            return False

        # CORS preflight carries no application data and browsers cannot attach
        # Authorization until the preflight succeeds. Explicit OPTIONS routes remain
        # protected.
        headers = Headers(scope=scope)
        return bool(headers.get("access-control-request-method"))
