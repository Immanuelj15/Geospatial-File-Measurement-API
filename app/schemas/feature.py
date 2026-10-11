from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from shapely.geometry.base import BaseGeometry


@dataclass
class ExtractedFeature:
    """Standardized in-memory representation of an individual extracted vector feature."""

    feature_index: int
    geometry_type: str
    geometry: Optional[BaseGeometry]
    geometry_geojson: Optional[Dict[str, Any]]
    properties: Dict[str, Any] = field(default_factory=dict)
    is_supported_geometry: bool = True
    is_valid_geometry: bool = True
    error_message: Optional[str] = None
