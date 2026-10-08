from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import health
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

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include base routes
    app.include_router(health.router)

    # Exception Handlers
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
            content={"error": "InternalApplicationError", "message": exc.message},
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
