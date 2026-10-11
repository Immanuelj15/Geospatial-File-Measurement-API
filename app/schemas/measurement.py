from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class FeatureMeasurementResult:
    """Standardized output of the measurement engine for an individual feature."""

    feature_index: int
    geometry_type: str
    geometry_geojson: Optional[Dict[str, Any]]
    properties: Dict[str, Any] = field(default_factory=dict)
    measurement_type: Optional[str] = None
    measurement_value: Optional[float] = None
    unit: Optional[str] = None
    status: str = "SUCCESS"
    error_message: Optional[str] = None
