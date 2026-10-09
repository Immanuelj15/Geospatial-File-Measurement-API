from pathlib import Path
import pytest

from app.core.exceptions import FileProcessingError
from app.services.geospatial_service import read_kml_file
from tests.fixtures.synthetic_geometries import (
    create_empty_kml,
    create_malformed_kml,
    create_multi_folder_kml,
    create_synthetic_kml,
)


def test_read_kml_file_mixed_geometries(tmp_path: Path) -> None:
    """Verify reading a KML file containing Point, LineString, and Polygon."""
    kml_path = tmp_path / "survey.kml"
    create_synthetic_kml(
        kml_path, include_point=True, include_line=True, include_polygon=True
    )

    gdf = read_kml_file(kml_path)

    assert len(gdf) == 3
    assert gdf.crs is not None
    assert "4326" in str(gdf.crs)

    geom_types = set(gdf.geometry.geom_type)
    assert "Point" in geom_types
    assert "LineString" in geom_types
    assert "Polygon" in geom_types

    # Verify properties/attributes extracted
    assert "Name" in gdf.columns or "name" in gdf.columns
    names = (gdf["Name"] if "Name" in gdf.columns else gdf["name"]).tolist()
    assert any("Survey Marker" in str(n) for n in names)


def test_read_kml_multi_folder(tmp_path: Path) -> None:
    """Verify features across multiple folders are aggregated."""
    kml_path = tmp_path / "multi_folder.kml"
    create_multi_folder_kml(kml_path)

    gdf = read_kml_file(kml_path)

    assert len(gdf) == 2
    geom_types = set(gdf.geometry.geom_type)
    assert "Point" in geom_types
    assert "Polygon" in geom_types


def test_read_kml_file_not_found(tmp_path: Path) -> None:
    """Verify non-existent file path raises FileProcessingError."""
    missing_path = tmp_path / "non_existent.kml"
    with pytest.raises(FileProcessingError) as exc_info:
        read_kml_file(missing_path)
    assert "File not found" in exc_info.value.message


def test_read_kml_empty_features(tmp_path: Path) -> None:
    """Verify KML with no placemarks raises FileProcessingError."""
    empty_path = tmp_path / "empty.kml"
    create_empty_kml(empty_path)

    with pytest.raises(FileProcessingError) as exc_info:
        read_kml_file(empty_path)
    assert (
        "no valid geospatial features" in exc_info.value.message.lower()
        or "0 features" in exc_info.value.message.lower()
    )


def test_read_kml_malformed_xml(tmp_path: Path) -> None:
    """Verify malformed XML raises FileProcessingError."""
    malformed_path = tmp_path / "corrupt.kml"
    create_malformed_kml(malformed_path)

    with pytest.raises(FileProcessingError) as exc_info:
        read_kml_file(malformed_path)
    assert "Failed to parse KML file" in exc_info.value.message
