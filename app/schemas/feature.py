from dataclasses import dataclass, field
from typing import Any

from shapely.geometry.base import BaseGeometry


@dataclass
class ExtractedFeature:
    """Standardized in-memory representation of an individual extracted vector feature."""

    feature_index: int
    geometry_type: str
    geometry: BaseGeometry | None
    geometry_geojson: dict[str, Any] | None
    properties: dict[str, Any] = field(default_factory=dict)
    is_supported_geometry: bool = True
    is_valid_geometry: bool = True
    error_message: str | None = None
