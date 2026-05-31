from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ..services.external_tools import ExternalToolError
from ..services.ocr_provider import OCRError


def create_app() -> FastAPI:
    app = FastAPI(title="Score Trans API", version="0.1.0")

    # CORS — development only. Production Electron uses file:// or custom scheme.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routers
    from .routers import health, convert, recognize, render, pipeline, files, history
    from .routers import export as export_router
    from .routers import settings as settings_router

    app.include_router(health.router)
    app.include_router(convert.router)
    app.include_router(recognize.router)
    app.include_router(render.router)
    app.include_router(pipeline.router)
    app.include_router(export_router.router)
    app.include_router(files.router)
    app.include_router(history.router)
    app.include_router(settings_router.router)

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

    @app.exception_handler(ValueError)
    async def validation_error_handler(request: Request, exc: ValueError):
        return JSONResponse(
            status_code=400,
            content={"error": str(exc), "stage": "convert"},
        )

    return app
