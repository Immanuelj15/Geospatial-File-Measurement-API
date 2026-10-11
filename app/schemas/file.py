from datetime import datetime
from typing import Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class FileDetailResponse(BaseModel):
    """Schema for file metadata, processing status, and metric counts."""

    id: uuid.UUID
    filename: str = Field(validation_alias="original_filename")
    file_type: str
    file_size_bytes: int
    status: str
    crs: Optional[str] = None
    feature_count: int = Field(validation_alias="total_features")
    successful_measurements: int
    failed_measurements: int
    unsupported_features: int
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )
