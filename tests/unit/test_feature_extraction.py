import datetime
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import GeometryCollection, LineString, Point, Polygon

from app.services.geospatial_service import (
    extract_features_from_dataframe,
    sanitize_properties,
)


def test_extract_features_valid_geometries() -> None:
    """Verify extraction of standard vector geometry types (Point, LineString, Polygon)."""
    geoms = [
        Point(77.5946, 12.9716),
        LineString([(77.590, 12.970), (77.595, 12.975)]),
        Polygon(
            [
                (77.590, 12.970),
                (77.595, 12.970),
                (77.595, 12.975),
                (77.590, 12.975),
                (77.590, 12.970),
            ]
        ),
    ]
    df = gpd.GeoDataFrame(
        {"name": ["Marker", "Line", "Parcel"], "id_code": [101, 102, 103]},
        geometry=geoms,
        crs="EPSG:4326",
    )

    features = extract_features_from_dataframe(df)

    assert len(features) == 3
    assert features[0].feature_index == 0
    assert features[0].geometry_type == "Point"
    assert features[0].is_supported_geometry is True
    assert features[0].is_valid_geometry is True
    assert features[0].geometry_geojson["type"] == "Point"
    assert features[0].properties["name"] == "Marker"
    assert features[0].properties["id_code"] == 101

    assert features[1].geometry_type == "LineString"
    assert features[2].geometry_type == "Polygon"


def test_sanitize_properties() -> None:
    """Verify property sanitizer normalizes types for clean JSON serialization."""
    raw_dict = {
        "int_val": np.int64(42),
        "float_val": np.float64(3.14159),
        "nan_val": float("nan"),
        "none_val": None,
        "pandas_na": pd.NA,
        "bool_val": np.bool_(True),
        "timestamp_val": pd.Timestamp("2026-10-09 10:00:00"),
        "date_val": datetime.date(2026, 10, 9),
        "bytes_val": b"hello_aereo",
        "geometry": Point(0, 0),
    }

    cleaned = sanitize_properties(raw_dict, geometry_col="geometry")

    assert "geometry" not in cleaned
    assert cleaned["int_val"] == 42
    assert isinstance(cleaned["int_val"], int)
    assert cleaned["float_val"] == 3.14159
    assert isinstance(cleaned["float_val"], float)
    assert cleaned["nan_val"] is None
    assert cleaned["none_val"] is None
    assert cleaned["pandas_na"] is None
    assert cleaned["bool_val"] is True
    assert "2026-10-09" in cleaned["timestamp_val"]
    assert cleaned["date_val"] == "2026-10-09"
    assert cleaned["bytes_val"] == "hello_aereo"


def test_extract_features_unsupported_geometry() -> None:
    """Verify unsupported geometry types (e.g., GeometryCollection) do not crash the parser."""
    geom_collection = GeometryCollection([Point(0, 0), LineString([(0, 0), (1, 1)])])
    valid_polygon = Polygon([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])

    df = gpd.GeoDataFrame(
        {"tag": ["unsupported_feat", "valid_feat"]},
        geometry=[geom_collection, valid_polygon],
        crs="EPSG:4326",
    )

    features = extract_features_from_dataframe(df)

    assert len(features) == 2
    # Unsupported feature is flagged cleanly
    assert features[0].is_supported_geometry is False
    assert features[0].geometry_type == "GeometryCollection"
    assert "Unsupported geometry type 'GeometryCollection'" in features[0].error_message

    # Other valid feature is unaffected
    assert features[1].is_supported_geometry is True
    assert features[1].is_valid_geometry is True
    assert features[1].geometry_type == "Polygon"


def test_extract_features_invalid_geometry() -> None:
    """Verify topologically invalid geometry (e.g. self-intersecting bowtie) is flagged."""
    # Self-intersecting bowtie polygon
    bowtie = Polygon([(0, 0), (1, 1), (1, 0), (0, 1), (0, 0)])
    assert not bowtie.is_valid

    df = gpd.GeoDataFrame(
        {"name": ["Bowtie"]},
        geometry=[bowtie],
        crs="EPSG:4326",
    )

    features = extract_features_from_dataframe(df)

    assert len(features) == 1
    assert features[0].is_valid_geometry is False
    assert "Invalid Polygon geometry" in features[0].error_message


def test_extract_features_none_geometry() -> None:
    """Verify rows with None/empty geometries are handled gracefully."""
    df = gpd.GeoDataFrame(
        {"name": ["Missing Geom"]},
        geometry=[None],
        crs="EPSG:4326",
    )

    features = extract_features_from_dataframe(df)

    assert len(features) == 1
    assert features[0].is_supported_geometry is False
    assert features[0].is_valid_geometry is False
    assert "missing or empty geometry" in features[0].error_message.lower()
