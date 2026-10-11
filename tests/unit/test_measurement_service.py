from shapely.geometry import LineString, MultiLineString, MultiPolygon, Point, Polygon

from app.db.models import FeatureStatus, MeasurementType
from app.schemas.feature import ExtractedFeature
from app.services.measurement_service import measure_dataset, measure_feature


def test_measure_polygon_area_exact() -> None:
    """Verify exact planar area computation for a known 100m x 100m square polygon."""
    square_poly = Polygon(
        [(0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0), (0.0, 0.0)]
    )
    feature = ExtractedFeature(
        feature_index=0,
        geometry_type="Polygon",
        geometry=square_poly,
        geometry_geojson={"type": "Polygon", "coordinates": []},
        properties={"parcel_name": "Plot 10"},
    )

    result = measure_feature(feature, square_poly)

    assert result.status == FeatureStatus.SUCCESS.value
    assert result.measurement_type == MeasurementType.AREA.value
    assert result.measurement_value == 10000.0
    assert result.unit == "m2"
    assert result.error_message is None


def test_measure_polygon_with_interior_hole_donut() -> None:
    """Verify area calculation on a polygon with an interior hole (donut polygon)."""
    # Outer ring: 100m x 100m (10,000 m2)
    outer = [(0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0), (0.0, 0.0)]
    # Inner hole: 20m x 20m (400 m2)
    inner = [(40.0, 40.0), (60.0, 40.0), (60.0, 60.0), (40.0, 60.0), (40.0, 40.0)]
    donut_poly = Polygon(shell=outer, holes=[inner])

    feature = ExtractedFeature(
        feature_index=1,
        geometry_type="Polygon",
        geometry=donut_poly,
        geometry_geojson=None,
    )

    result = measure_feature(feature, donut_poly)

    assert result.status == FeatureStatus.SUCCESS.value
    assert result.measurement_type == MeasurementType.AREA.value
    assert result.measurement_value == 9600.0  # 10,000 - 400 = 9600
    assert result.unit == "m2"


def test_measure_3d_coordinates_z_axis_handling() -> None:
    """Verify 3D coordinates (with Z elevation) are measured accurately in 2D planar space."""
    # 3D LineString with Z elevation values (10m, 20m, 30m)
    line_3d = LineString([(0.0, 0.0, 10.0), (100.0, 0.0, 20.0), (100.0, 50.0, 30.0)])
    feature_line = ExtractedFeature(
        feature_index=2,
        geometry_type="LineString",
        geometry=line_3d,
        geometry_geojson=None,
    )
    res_line = measure_feature(feature_line, line_3d)
    assert res_line.status == FeatureStatus.SUCCESS.value
    assert res_line.measurement_value == 150.0  # Planar length (100 + 50)
    assert res_line.unit == "m"

    # 3D Polygon with Z elevation
    poly_3d = Polygon(
        [
            (0.0, 0.0, 50.0),
            (10.0, 0.0, 50.0),
            (10.0, 10.0, 50.0),
            (0.0, 10.0, 50.0),
            (0.0, 0.0, 50.0),
        ]
    )
    feature_poly = ExtractedFeature(
        feature_index=3,
        geometry_type="Polygon",
        geometry=poly_3d,
        geometry_geojson=None,
    )
    res_poly = measure_feature(feature_poly, poly_3d)
    assert res_poly.status == FeatureStatus.SUCCESS.value
    assert res_poly.measurement_value == 100.0
    assert res_poly.unit == "m2"


def test_measure_multipolygon_area() -> None:
    """Verify area calculation on multi-part polygons."""
    poly1 = Polygon(
        [(0.0, 0.0), (50.0, 0.0), (50.0, 50.0), (0.0, 50.0), (0.0, 0.0)]
    )  # 2500 m2
    poly2 = Polygon(
        [(100.0, 100.0), (150.0, 100.0), (150.0, 150.0), (100.0, 150.0), (100.0, 100.0)]
    )  # 2500 m2
    multi_poly = MultiPolygon([poly1, poly2])

    feature = ExtractedFeature(
        feature_index=4,
        geometry_type="MultiPolygon",
        geometry=multi_poly,
        geometry_geojson={"type": "MultiPolygon", "coordinates": []},
    )

    result = measure_feature(feature, multi_poly)

    assert result.status == FeatureStatus.SUCCESS.value
    assert result.measurement_type == MeasurementType.AREA.value
    assert result.measurement_value == 5000.0
    assert result.unit == "m2"


def test_measure_linestring_length_exact() -> None:
    """Verify exact length computation for a known 150m linear path."""
    line = LineString([(0.0, 0.0), (100.0, 0.0), (100.0, 50.0)])  # 100m + 50m = 150m
    feature = ExtractedFeature(
        feature_index=5,
        geometry_type="LineString",
        geometry=line,
        geometry_geojson={"type": "LineString", "coordinates": []},
    )

    result = measure_feature(feature, line)

    assert result.status == FeatureStatus.SUCCESS.value
    assert result.measurement_type == MeasurementType.LENGTH.value
    assert result.measurement_value == 150.0
    assert result.unit == "m"
    assert result.error_message is None


def test_measure_multilinestring_length() -> None:
    """Verify length computation on multi-part lines."""
    line1 = LineString([(0.0, 0.0), (50.0, 0.0)])  # 50m
    line2 = LineString([(100.0, 0.0), (200.0, 0.0)])  # 100m
    multi_line = MultiLineString([line1, line2])

    feature = ExtractedFeature(
        feature_index=6,
        geometry_type="MultiLineString",
        geometry=multi_line,
        geometry_geojson={"type": "MultiLineString", "coordinates": []},
    )

    result = measure_feature(feature, multi_line)

    assert result.status == FeatureStatus.SUCCESS.value
    assert result.measurement_type == MeasurementType.LENGTH.value
    assert result.measurement_value == 150.0
    assert result.unit == "m"


def test_measure_point_passthrough() -> None:
    """Verify Point geometries return SUCCESS with null measurement value and null unit."""
    pt = Point(500000.0, 1500000.0)
    feature = ExtractedFeature(
        feature_index=7,
        geometry_type="Point",
        geometry=pt,
        geometry_geojson={"type": "Point", "coordinates": [500000.0, 1500000.0]},
    )

    result = measure_feature(feature, pt)

    assert result.status == FeatureStatus.SUCCESS.value
    assert result.measurement_type is None
    assert result.measurement_value is None
    assert result.unit is None
    assert result.error_message is None


def test_measure_unsupported_geometry() -> None:
    """Verify unsupported geometry returns UNSUPPORTED status without crashing."""
    feature = ExtractedFeature(
        feature_index=8,
        geometry_type="GeometryCollection",
        geometry=None,
        geometry_geojson=None,
        is_supported_geometry=False,
        error_message="Unsupported geometry type 'GeometryCollection'.",
    )

    result = measure_feature(feature, None)

    assert result.status == FeatureStatus.UNSUPPORTED.value
    assert result.measurement_type is None
    assert result.measurement_value is None
    assert result.unit is None
    assert "Unsupported geometry type 'GeometryCollection'" in result.error_message


def test_measure_invalid_geometry() -> None:
    """Verify topologically invalid geometry returns FAILED status with diagnostic error."""
    feature = ExtractedFeature(
        feature_index=9,
        geometry_type="Polygon",
        geometry=None,
        geometry_geojson=None,
        is_valid_geometry=False,
        error_message="Invalid Polygon geometry (topological violation).",
    )

    result = measure_feature(feature, None)

    assert result.status == FeatureStatus.FAILED.value
    assert result.measurement_type == MeasurementType.AREA.value
    assert result.measurement_value is None
    assert result.unit is None
    assert "Invalid Polygon geometry" in result.error_message


def test_measure_dataset_batch() -> None:
    """Verify batch measurement processing across mixed geometries."""
    poly = Polygon(
        [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0), (0.0, 0.0)]
    )  # 100 m2
    line = LineString([(0.0, 0.0), (25.0, 0.0)])  # 25 m
    point = Point(10.0, 10.0)

    f1 = ExtractedFeature(
        feature_index=0, geometry_type="Polygon", geometry=poly, geometry_geojson=None
    )
    f2 = ExtractedFeature(
        feature_index=1,
        geometry_type="LineString",
        geometry=line,
        geometry_geojson=None,
    )
    f3 = ExtractedFeature(
        feature_index=2, geometry_type="Point", geometry=point, geometry_geojson=None
    )

    results = measure_dataset([f1, f2, f3], [poly, line, point])

    assert len(results) == 3
    assert results[0].measurement_value == 100.0
    assert results[1].measurement_value == 25.0
    assert results[2].measurement_value is None
