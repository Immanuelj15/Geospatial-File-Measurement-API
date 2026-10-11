from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


@dataclass
class FeatureMeasurementResult:
    """Standardized internal output of the measurement engine for an individual feature."""

    feature_index: int
    geometry_type: str
    geometry_geojson: Optional[Dict[str, Any]]
    properties: Dict[str, Any] = field(default_factory=dict)
    measurement_type: Optional[str] = None
    measurement_value: Optional[float] = None
    unit: Optional[str] = None
    status: str = "SUCCESS"
    error_message: Optional[str] = None


class FeatureMeasurementResponse(BaseModel):
    """API response model for an individual feature measurement."""

    id: uuid.UUID
    feature_id: int = Field(validation_alias="feature_index")
    geometry_type: str
    measurement_type: Optional[str] = None
    measurement_value: Optional[float] = None
    unit: Optional[str] = Field(default=None, validation_alias="measurement_unit")
    status: str
    error: Optional[str] = Field(default=None, validation_alias="error_message")
    properties: Optional[Dict[str, Any]] = None
    geometry: Optional[Dict[str, Any]] = Field(
        default=None, validation_alias="geometry_geojson"
    )

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
    items: List[FeatureMeasurementResponse]

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )
