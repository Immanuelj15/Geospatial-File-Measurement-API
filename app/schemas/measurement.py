import uuid
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


@dataclass
class FeatureMeasurementResult:
    """Standardized internal output of the measurement engine for an individual feature."""

    feature_index: int
    geometry_type: str
    geometry_geojson: dict[str, Any] | None
    properties: dict[str, Any] = field(default_factory=dict)
    measurement_type: str | None = None
    measurement_value: float | None = None
    unit: str | None = None
    status: str = "SUCCESS"
    error_message: str | None = None


class FeatureMeasurementResponse(BaseModel):
    """API response model for an individual feature measurement."""

    id: uuid.UUID
    feature_id: int = Field(validation_alias="feature_index")
    geometry_type: str
    measurement_type: str | None = None
    measurement_value: float | None = None
    unit: str | None = Field(default=None, validation_alias="measurement_unit")
    status: str
    error: str | None = Field(default=None, validation_alias="error_message")
    properties: dict[str, Any] | None = None
    geometry: dict[str, Any] | None = Field(default=None, validation_alias="geometry_geojson")

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )


class PaginatedMeasurementsResponse(BaseModel):
    """API response model for paginated feature measurements."""

    file_id: uuid.UUID
    total: int
    offset: int
    limit: int
    items: list[FeatureMeasurementResponse]

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )
