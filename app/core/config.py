from functools import lru_cache
from pathlib import Path
from typing import Set

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    # Project metadata
    PROJECT_NAME: str = Field(default="Geospatial File Measurement API")
    ENVIRONMENT: str = Field(default="development")
    DEBUG: bool = Field(default=True)
    API_V1_PREFIX: str = Field(default="/api")

    # Server configuration
    HOST: str = Field(default="0.0.0.0")
    PORT: int = Field(default=8000)

    # Database configuration
    DATABASE_URL: str = Field(
        default="postgresql+psycopg2://postgres:postgres@localhost:5432/geospatial_db"
    )

    # Storage & Upload configuration
    UPLOAD_DIR: Path = Field(default=Path("uploads"))
    MAX_UPLOAD_SIZE_BYTES: int = Field(default=25 * 1024 * 1024)  # 25 MB
    ALLOWED_EXTENSIONS: Set[str] = Field(default={".kml", ".zip"})

    # Logging
    LOG_LEVEL: str = Field(default="INFO")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )


@lru_cache
def get_settings() -> Settings:
    """Provide cached application settings instance."""
    return Settings()
