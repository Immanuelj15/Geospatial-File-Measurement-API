from shapely.geometry.base import BaseGeometry

from app.core.logging import logger
from app.db.models import FeatureStatus, MeasurementType
from app.schemas.feature import ExtractedFeature
from app.schemas.measurement import FeatureMeasurementResult

AREA_GEOMETRIES = {"Polygon", "MultiPolygon"}
LENGTH_GEOMETRIES = {"LineString", "MultiLineString"}
POINT_GEOMETRIES = {"Point", "MultiPoint"}


def measure_feature(
    feature: ExtractedFeature,
    projected_geometry: BaseGeometry | None,
) -> FeatureMeasurementResult:
    """Compute metric measurement (area or length) for an individual vector feature.

    Guarantees that an individual feature failure (e.g. invalid topology, math error,
    or unsupported type) returns a structured failure without throwing an unhandled exception.
    """
    # Case 1: Geometry was flagged as unsupported
    if not feature.is_supported_geometry:
        return FeatureMeasurementResult(
            feature_index=feature.feature_index,
            geometry_type=feature.geometry_type,
            geometry_geojson=feature.geometry_geojson,
            properties=feature.properties,
            measurement_type=None,
            measurement_value=None,
            unit=None,
            status=FeatureStatus.UNSUPPORTED.value,
            error_message=feature.error_message
            or f"Unsupported geometry type '{feature.geometry_type}'.",
        )

    # Case 2: Geometry is missing, empty, or flagged as topologically invalid
    if not feature.is_valid_geometry or projected_geometry is None:
        expected_type = None
        if feature.geometry_type in AREA_GEOMETRIES:
            expected_type = MeasurementType.AREA.value
        elif feature.geometry_type in LENGTH_GEOMETRIES:
            expected_type = MeasurementType.LENGTH.value

        return FeatureMeasurementResult(
            feature_index=feature.feature_index,
            geometry_type=feature.geometry_type,
            geometry_geojson=feature.geometry_geojson,
            properties=feature.properties,
            measurement_type=expected_type,
            measurement_value=None,
            unit=None,
            status=FeatureStatus.FAILED.value,
            error_message=feature.error_message or "Geometry is invalid or missing.",
        )

    # Case 3: Measurement execution
    try:
        geom_type = projected_geometry.geom_type

        # Polygon -> Area (m2)
        if geom_type in AREA_GEOMETRIES:
            raw_area = float(projected_geometry.area)
            rounded_area = round(raw_area, 2)
            return FeatureMeasurementResult(
                feature_index=feature.feature_index,
                geometry_type=feature.geometry_type,
                geometry_geojson=feature.geometry_geojson,
                properties=feature.properties,
                measurement_type=MeasurementType.AREA.value,
                measurement_value=rounded_area,
                unit="m2",
                status=FeatureStatus.SUCCESS.value,
                error_message=None,
            )

        # LineString -> Length (m)
        if geom_type in LENGTH_GEOMETRIES:
            raw_length = float(projected_geometry.length)
            rounded_length = round(raw_length, 2)
            return FeatureMeasurementResult(
                feature_index=feature.feature_index,
                geometry_type=feature.geometry_type,
                geometry_geojson=feature.geometry_geojson,
                properties=feature.properties,
                measurement_type=MeasurementType.LENGTH.value,
                measurement_value=rounded_length,
                unit="m",
                status=FeatureStatus.SUCCESS.value,
                error_message=None,
            )

        # Point -> No measurement required
        if geom_type in POINT_GEOMETRIES:
            return FeatureMeasurementResult(
                feature_index=feature.feature_index,
                geometry_type=feature.geometry_type,
                geometry_geojson=feature.geometry_geojson,
                properties=feature.properties,
                measurement_type=None,
                measurement_value=None,
                unit=None,
                status=FeatureStatus.SUCCESS.value,
                error_message=None,
            )

        # Fallback for unrecognized geometry type
        return FeatureMeasurementResult(
            feature_index=feature.feature_index,
            geometry_type=feature.geometry_type,
            geometry_geojson=feature.geometry_geojson,
            properties=feature.properties,
            measurement_type=None,
            measurement_value=None,
            unit=None,
            status=FeatureStatus.UNSUPPORTED.value,
            error_message=f"Unsupported geometry type '{geom_type}' encountered during measurement.",
        )

    except Exception as exc:
        logger.error(
            "Measurement error on feature %d (%s): %s",
            feature.feature_index,
            feature.geometry_type,
            str(exc),
            exc_info=True,
        )
        return FeatureMeasurementResult(
            feature_index=feature.feature_index,
            geometry_type=feature.geometry_type,
            geometry_geojson=feature.geometry_geojson,
            properties=feature.properties,
            measurement_type=None,
            measurement_value=None,
            unit=None,
            status=FeatureStatus.FAILED.value,
            error_message=f"Measurement computation error: {str(exc)}",
        )


def measure_dataset(
    extracted_features: list[ExtractedFeature],
    projected_geometries: list[BaseGeometry | None],
) -> list[FeatureMeasurementResult]:
    """Perform batch measurements matching extracted features to projected geometries."""
    results: list[FeatureMeasurementResult] = []
    for feature, proj_geom in zip(extracted_features, projected_geometries, strict=False):
        res = measure_feature(feature, proj_geom)
        results.append(res)
    return results
