from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.routes import files, health
from app.core.config import get_settings
from app.core.exceptions import (
    AppBaseException,
    EntityNotFoundError,
    FileValidationError,
)
from app.core.logging import logger


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup and shutdown events."""
    settings = get_settings()
    # Ensure upload directory exists safely
    settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    logger.info(
        "Application startup complete. Environment: %s, Uploads dir: %s",
        settings.ENVIRONMENT,
        settings.UPLOAD_DIR.resolve(),
    )
    yield
    logger.info("Application shutting down.")


def create_app() -> FastAPI:
    """Application factory for FastAPI instance."""
    settings = get_settings()

    app = FastAPI(
        title=settings.PROJECT_NAME,
        version="1.0.0",
        description="Production-grade API for geospatial vector file ingestion and projected metric measurements.",
        lifespan=lifespan,
    )

    # Security Headers Middleware
    @app.middleware("http")
    async def security_headers_middleware(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

    # CORS configuration
    is_wildcard = settings.CORS_ORIGINS == ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=not is_wildcard,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routes
    app.include_router(health.router)
    app.include_router(files.router, prefix=settings.API_V1_PREFIX)

    # Exception Handlers
    @app.exception_handler(RequestValidationError)
    async def request_validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        logger.warning("Request schema validation failed: %s", exc.errors())
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "ValidationError",
                "message": "The request contained invalid parameters or payload.",
                "details": exc.errors(),
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def starlette_http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        logger.info("HTTP exception %d: %s", exc.status_code, exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": f"HTTP_{exc.status_code}",
                "message": str(exc.detail),
                "details": {},
            },
        )

    @app.exception_handler(FileValidationError)
    async def file_validation_exception_handler(
        request: Request, exc: FileValidationError
    ) -> JSONResponse:
        logger.warning(
            "File validation error: %s (details: %s)", exc.message, exc.details
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": "FileValidationError",
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(EntityNotFoundError)
    async def entity_not_found_exception_handler(
        request: Request, exc: EntityNotFoundError
    ) -> JSONResponse:
        logger.info("Entity not found: %s", exc.message)
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "error": "EntityNotFoundError",
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(AppBaseException)
    async def app_base_exception_handler(
        request: Request, exc: AppBaseException
    ) -> JSONResponse:
        logger.error("Application domain error: %s", exc.message, exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "InternalApplicationError",
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.error("Unhandled server exception: %s", str(exc), exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "InternalServerError",
                "message": "An unexpected error occurred.",
            },
        )

    return app


app = create_app()
