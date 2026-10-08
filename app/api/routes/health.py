from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.config import Settings, get_settings

router = APIRouter(tags=["Health"])


class HealthResponse(BaseModel):
    status: str
    project: str
    environment: str


@router.get("/health", response_model=HealthResponse, summary="Service Health Check")
async def health_check(settings: Settings = Depends(get_settings)) -> HealthResponse:
    """Return application health status and environment."""
    return HealthResponse(
        status="healthy",
        project=settings.PROJECT_NAME,
        environment=settings.ENVIRONMENT,
    )
