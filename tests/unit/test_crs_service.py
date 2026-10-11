import geopandas as gpd
from pyproj import CRS
from shapely.geometry import Polygon

from app.services.crs_service import (
    calculate_utm_epsg,
    determine_optimal_projected_crs,
    parse_crs,
    reproject_dataframe_for_measurement,
    transform_geometry,
)


def test_calculate_utm_epsg_quadrants() -> None:
    """Verify UTM zone calculation across all geographic quadrants and polar zones."""
    # Bangalore (India): 77.59° E, 12.97° N -> UTM Zone 43N (EPSG 32643)
    assert calculate_utm_epsg(77.5946, 12.9716) == 32643

    # Sydney (Australia): 151.21° E, 33.87° S -> UTM Zone 56S (EPSG 32756)
    assert calculate_utm_epsg(151.2093, -33.8688) == 32756

    # New York (USA): 74.01° W, 40.71° N -> UTM Zone 18N (EPSG 32618)
    assert calculate_utm_epsg(-74.0060, 40.7128) == 32618

    # Santiago (Chile): 70.67° W, 33.45° S -> UTM Zone 19S (EPSG 32719)
    assert calculate_utm_epsg(-70.6693, -33.4489) == 32719

    # Polar Arctic (> 84° N) -> UPS North (EPSG 32661)
    assert calculate_utm_epsg(10.0, 85.0) == 32661

    # Polar Antarctic (< -80° S) -> UPS South (EPSG 32761)
    assert calculate_utm_epsg(10.0, -82.0) == 32761


def test_parse_crs() -> None:
    """Verify parsing various CRS formats."""
    assert parse_crs("EPSG:4326") == CRS.from_epsg(4326)
    assert parse_crs(32643) == CRS.from_epsg(32643)
    assert parse_crs(None) is None
    assert parse_crs("not_a_real_crs_string") is None


def test_determine_optimal_projected_crs_already_projected() -> None:
    """Verify already projected CRS is preserved to avoid unnecessary reprojection."""
    source_projected = CRS.from_epsg(32643)
    target_crs, needs_reprojection = determine_optimal_projected_crs(
        source_crs=source_projected,
        centroid_lon=77.59,
        centroid_lat=12.97,
    )
    assert needs_reprojection is False
    assert target_crs == source_projected


def test_determine_optimal_projected_crs_geographic() -> None:
    """Verify geographic CRS triggers UTM zone projection."""
    source_geo = CRS.from_epsg(4326)
    target_crs, needs_reprojection = determine_optimal_projected_crs(
        source_crs=source_geo,
        centroid_lon=77.59,
        centroid_lat=12.97,
    )
    assert needs_reprojection is True
    assert target_crs.to_epsg() == 32643


def test_transform_geometry_preserves_shape() -> None:
    """Verify geometry reprojection converts angular degrees into metric planar meters."""
    # Polygon in Bangalore (EPSG:4326 degrees)
    poly_degrees = Polygon(
        [
            (77.590, 12.970),
            (77.595, 12.970),
            (77.595, 12.975),
            (77.590, 12.975),
            (77.590, 12.970),
        ]
    )
    source_crs = CRS.from_epsg(4326)
    target_crs = CRS.from_epsg(32643)

    poly_meters = transform_geometry(poly_degrees, source_crs, target_crs)

    assert poly_meters.is_valid
    # In UTM zone 43N, X is around 780,000 m, Y is around 1,430,000 m
    minx, miny, maxx, maxy = poly_meters.bounds
    assert minx > 100000.0
    assert miny > 100000.0


def test_reproject_dataframe_for_measurement() -> None:
    """Verify GeoDataFrame reprojection pipeline returns projected data and CRS labels."""
    poly = Polygon(
        [
            (77.590, 12.970),
            (77.595, 12.970),
            (77.595, 12.975),
            (77.590, 12.975),
            (77.590, 12.970),
        ]
    )
    gdf = gpd.GeoDataFrame({"name": ["Test Site"]}, geometry=[poly], crs="EPSG:4326")

    proj_gdf, detected_str, measurement_str = reproject_dataframe_for_measurement(gdf)

    assert "4326" in detected_str
    assert "32643" in measurement_str
    assert proj_gdf.crs.to_epsg() == 32643
    # Coordinates are now in meters
    assert proj_gdf.geometry.iloc[0].bounds[0] > 100000.0


def test_reproject_dataframe_missing_crs_fallback() -> None:
    """Verify missing CRS defaults to EPSG:4326 and reprojects successfully."""
    poly = Polygon(
        [
            (77.590, 12.970),
            (77.595, 12.970),
            (77.595, 12.975),
            (77.590, 12.975),
            (77.590, 12.970),
        ]
    )
    gdf_unprojected = gpd.GeoDataFrame(
        {"name": ["No CRS Site"]}, geometry=[poly], crs=None
    )

    proj_gdf, detected_str, measurement_str = reproject_dataframe_for_measurement(
        gdf_unprojected
    )

    assert "UNSPECIFIED" in detected_str
    assert "32643" in measurement_str
    assert proj_gdf.crs.to_epsg() == 32643
