from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from score_trans.config.settings import API_TITLE, API_VERSION, CORS_ORIGINS

from ..exec.tasks.actions import TaskActions
from ..models.common.errors import AITranscriptionError, ExternalToolError, OCRError


def create_app() -> FastAPI:
    app = FastAPI(
        title=API_TITLE,
        version=API_VERSION,
    )
    app.state.task_actions = TaskActions()

    # CORS — development only. Production Electron uses file:// or custom scheme.
    _raw_origins = CORS_ORIGINS
    allow_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routers
    from .ai import routes as ai
    from .health import routes as health
    from .convert import routes as convert
    from .recognize import routes as recognize
    from .render import routes as render
    from .pipeline import routes as pipeline
    from .files import routes as files
    from .history import routes as history
    from .export import routes as export_router
    from .settings import routes as settings_router
    from .tasks import routes as tasks

    app.include_router(ai.router)
    app.include_router(health.router)
    app.include_router(convert.router)
    app.include_router(recognize.router)
    app.include_router(render.router)
    app.include_router(pipeline.router)
    app.include_router(export_router.router)
    app.include_router(files.router)
    app.include_router(history.router)
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
    async def ai_transcription_error_handler(request: Request, exc: AITranscriptionError):
        return JSONResponse(
            status_code=502,
            content={"error": str(exc), "stage": "ai"},
        )

    @app.exception_handler(ValueError)
    async def validation_error_handler(request: Request, exc: ValueError):
        return JSONResponse(
            status_code=400,
            content={"error": str(exc), "stage": "convert"},
        )

    @app.exception_handler(FileNotFoundError)
    async def file_not_found_error_handler(request: Request, exc: FileNotFoundError):
        return JSONResponse(
            status_code=404,
            content={"error": str(exc), "stage": "files"},
        )

    return app
