from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from score_trans.config.settings import (
    API_AUTH_DISABLED,
    API_TITLE,
    API_TOKEN,
    API_VERSION,
    CORS_ORIGINS,
    MAX_UPLOAD_REQUEST_BYTES,
)

from .auth import BearerAuthMiddleware, validate_api_token
from .request_limits import RequestBodyLimitMiddleware
from ..exec.tasks.actions import TaskActions
from ..models.common.errors import (
    AITranscriptionError,
    ExternalToolError,
    OCRError,
    RenderError,
    UploadTooLargeError,
)


LOCAL_DEV_ORIGIN_REGEX = r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    _init_task_state(app)
    try:
        yield
    finally:
        await _wait_for_background_tasks(app)


def create_app(
    *,
    api_token: str | None = None,
    auth_disabled: bool | None = None,
    max_upload_request_bytes: int | None = None,
) -> FastAPI:
    effective_token = API_TOKEN if api_token is None else api_token
    effective_auth_disabled = (
        API_AUTH_DISABLED if auth_disabled is None else auth_disabled
    )
    effective_max_upload_request_bytes = (
        MAX_UPLOAD_REQUEST_BYTES
        if max_upload_request_bytes is None
        else max_upload_request_bytes
    )
    validate_api_token(effective_token, disabled=effective_auth_disabled)

    app = FastAPI(
        title=API_TITLE,
        version=API_VERSION,
        lifespan=lifespan,
    )
    _init_task_state(app)

    # CORS — development + Electron production (file:// / null origin).
    _raw_origins = CORS_ORIGINS
    allow_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]
    # Electron packaged app loads from file:// or custom protocol, whose Origin is "null".
    if "null" not in allow_origins:
        allow_origins.append("null")
    app.add_middleware(
        RequestBodyLimitMiddleware,
        max_bytes=effective_max_upload_request_bytes,
    )
    app.add_middleware(
        BearerAuthMiddleware,
        token=effective_token,
        disabled=effective_auth_disabled,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_origin_regex=LOCAL_DEV_ORIGIN_REGEX,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routers
    from .ai import routes as ai
    from .health import routes as health
    from .convert import routes as convert
    from .correct import routes as correct
    from .recognize import routes as recognize
    from .render import routes as render
    from .pipeline import routes as pipeline
    from .files import routes as files
    from .history import routes as history
    from .notation import routes as notation
    from .export import routes as export_router
    from .settings import routes as settings_router
    from .tasks import routes as tasks

    app.include_router(ai.router)
    app.include_router(health.router)
    app.include_router(convert.router)
    app.include_router(correct.router)
    app.include_router(recognize.router)
    app.include_router(render.router)
    app.include_router(pipeline.router)
    app.include_router(export_router.router)
    app.include_router(files.router)
    app.include_router(history.router)
    app.include_router(notation.router)
    app.include_router(settings_router.router)
    app.include_router(tasks.router)

    # Exception handlers — unified error format
    @app.exception_handler(ExternalToolError)
    async def external_tool_error_handler(request: Request, exc: ExternalToolError):
        return JSONResponse(
            status_code=502,
            content={"error": str(exc), "stage": "audiveris"},
        )

    @app.exception_handler(OCRError)
    async def ocr_error_handler(request: Request, exc: OCRError):
        return JSONResponse(
            status_code=502,
            content={"error": str(exc), "stage": "ocr"},
        )

    @app.exception_handler(AITranscriptionError)
    async def ai_transcription_error_handler(
        request: Request, exc: AITranscriptionError
    ):
        return JSONResponse(
            status_code=502,
            content={"error": str(exc), "stage": "ai"},
        )

    @app.exception_handler(RenderError)
    async def render_error_handler(request: Request, exc: RenderError):
        return JSONResponse(
            status_code=500,
            content={"error": str(exc), "stage": "render"},
        )

    @app.exception_handler(UploadTooLargeError)
    async def upload_too_large_handler(request: Request, exc: UploadTooLargeError):
        return JSONResponse(
            status_code=413,
            content={"error": str(exc), "stage": "upload"},
        )

    @app.exception_handler(ValueError)
    async def validation_error_handler(request: Request, exc: ValueError):
        return JSONResponse(
            status_code=400,
            content={"error": str(exc), "stage": "validation"},
        )

    @app.exception_handler(FileNotFoundError)
    async def file_not_found_error_handler(request: Request, exc: FileNotFoundError):
        return JSONResponse(
            status_code=404,
            content={"error": str(exc), "stage": "files"},
        )

    return app


def _init_task_state(app: FastAPI) -> None:
    if getattr(app.state, "task_actions", None) is None:
        app.state.task_actions = TaskActions()
    if getattr(app.state, "background_tasks", None) is None:
        app.state.background_tasks = set()
    app.state.accepting_background_tasks = True


async def _wait_for_background_tasks(app: FastAPI) -> None:
    background_tasks = getattr(app.state, "background_tasks", set())
    app.state.accepting_background_tasks = False
    tracked_tasks = set(background_tasks)
    if not tracked_tasks:
        return
    try:
        await asyncio.gather(*tracked_tasks, return_exceptions=True)
    finally:
        background_tasks.difference_update(tracked_tasks)
