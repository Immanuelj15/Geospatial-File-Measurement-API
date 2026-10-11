import math
from typing import Any

import geopandas as gpd
from pyproj import CRS, Transformer
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform

from app.core.exceptions import CRSTransformationError
from app.core.logging import logger

# Polar latitude thresholds where UTM is undefined and UPS is used
MAX_UTM_LAT = 84.0
MIN_UTM_LAT = -80.0
UPS_NORTH_EPSG = 32661
UPS_SOUTH_EPSG = 32761


def parse_crs(crs_input: Any) -> CRS | None:
    """Parse various CRS representations into a pyproj.CRS instance.

    Returns None if input is None or cannot be parsed.
    """
    if crs_input is None:
        return None

    if isinstance(crs_input, CRS):
        return crs_input

    try:
        return CRS.from_user_input(crs_input)
    except Exception as exc:
        logger.warning("Failed to parse CRS input '%s': %s", crs_input, str(exc))
        return None


def calculate_utm_epsg(lon: float, lat: float) -> int:
    """Calculate the optimal projected EPSG code based on longitude and latitude.

    For latitudes between -80 and +84, selects the appropriate UTM zone:
      Zone = floor((lon + 180) / 6) + 1
      Northern Hemisphere: EPSG 32600 + Zone
      Southern Hemisphere: EPSG 32700 + Zone
    For extreme polar latitudes, selects Universal Polar Stereographic (UPS).
    """
    # Normalize longitude to [-180, 180)
    norm_lon = (lon + 180.0) % 360.0 - 180.0

    # Polar checks
    if lat > MAX_UTM_LAT:
        return UPS_NORTH_EPSG
    if lat < MIN_UTM_LAT:
        return UPS_SOUTH_EPSG

    # UTM Zone calculation
    zone = int(math.floor((norm_lon + 180.0) / 6.0)) + 1
    # Clamping zone between 1 and 60
    zone = max(1, min(60, zone))

    if lat >= 0.0:
        return 32600 + zone
    return 32700 + zone


def determine_optimal_projected_crs(
    source_crs: CRS | None,
    centroid_lon: float,
    centroid_lat: float,
) -> tuple[CRS, bool]:
    """Determine the target projected CRS for metric measurements.

    Returns:
        (target_crs, needs_reprojection)
    If source_crs is already projected and has linear units (e.g. meters),
    it is preserved (needs_reprojection=False).
    If source_crs is geographic (or missing), returns the local UTM/UPS CRS (needs_reprojection=True).
    """
    # Case 1: Already projected and suitable for planar measurement
    if source_crs is not None and source_crs.is_projected:
        logger.info(
            "Source CRS '%s' is already projected. Preserving for measurement.",
            source_crs.to_string(),
        )
        return source_crs, False

    # Case 2: Geographic CRS (or missing) -> calculate local UTM/UPS
    target_epsg = calculate_utm_epsg(centroid_lon, centroid_lat)
    target_crs = CRS.from_epsg(target_epsg)
    logger.info(
        "Source CRS is geographic or unassigned. Selected local projected CRS EPSG:%d for centroid (%.4f, %.4f).",
        target_epsg,
        centroid_lon,
        centroid_lat,
    )
    return target_crs, True


def transform_geometry(
    geometry: BaseGeometry,
    source_crs: CRS,
    target_crs: CRS,
) -> BaseGeometry:
    """Transform a Shapely geometry from source_crs to target_crs.

    Uses pyproj.Transformer with always_xy=True for consistent (x, y) / (lon, lat) ordering.
    Raises CRSTransformationError if coordinate transformation fails.
    """
    if source_crs == target_crs:
        return geometry

    try:
        transformer = Transformer.from_crs(source_crs, target_crs, always_xy=True)
        return transform(transformer.transform, geometry)
    except Exception as exc:
        logger.error(
            "Failed to reproject geometry from %s to %s: %s",
            source_crs,
            target_crs,
            str(exc),
        )
        raise CRSTransformationError(
            message=f"Reprojection failed: {str(exc)}",
            details={
                "source_crs": source_crs.to_string(),
                "target_crs": target_crs.to_string(),
                "error": str(exc),
            },
        ) from exc


def reproject_dataframe_for_measurement(
    gdf: gpd.GeoDataFrame,
) -> tuple[gpd.GeoDataFrame, str, str]:
    """Inspect GeoDataFrame CRS, determine optimal projected CRS, and reproject for measurement.

    Returns:
        (projected_gdf, detected_crs_display, measurement_crs_display)
    """
    source_crs = parse_crs(gdf.crs)
    detected_crs_str = source_crs.to_string() if source_crs else "UNSPECIFIED (Assumed EPSG:4326)"

    # Fallback to EPSG:4326 if source CRS was completely unassigned
    working_source_crs = source_crs if source_crs is not None else CRS.from_epsg(4326)

    # Compute dataset geographic centroid for UTM selection
    if working_source_crs.is_geographic:
        # Reproject centroid calculation to EPSG:4326 if needed
        bounds = gdf.total_bounds  # [minx, miny, maxx, maxy]
        center_lon = (bounds[0] + bounds[2]) / 2.0
        center_lat = (bounds[1] + bounds[3]) / 2.0
    else:
        # Already projected: transform centroid to WGS84 just to get lon/lat if needed, or preserve
        to_wgs84 = Transformer.from_crs(working_source_crs, CRS.from_epsg(4326), always_xy=True)
        bounds = gdf.total_bounds
        mid_x = (bounds[0] + bounds[2]) / 2.0
        mid_y = (bounds[1] + bounds[3]) / 2.0
        center_lon, center_lat = to_wgs84.transform(mid_x, mid_y)

    target_crs, needs_reprojection = determine_optimal_projected_crs(
        source_crs=working_source_crs,
        centroid_lon=center_lon,
        centroid_lat=center_lat,
    )

    measurement_crs_str = target_crs.to_string()

    if needs_reprojection:
        logger.info(
            "Reprojecting dataset from %s to %s for planar measurements.",
            detected_crs_str,
            measurement_crs_str,
        )
        # If source CRS was missing, set it before reprojection
        if gdf.crs is None:
            gdf = gdf.set_crs(working_source_crs)
        projected_gdf = gdf.to_crs(target_crs)
    else:
        projected_gdf = gdf

    return projected_gdf, detected_crs_str, measurement_crs_str
