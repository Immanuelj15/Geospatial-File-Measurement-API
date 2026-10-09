from pathlib import Path
import zipfile
import pytest

from app.core.exceptions import FileProcessingError, FileValidationError
from app.db.models import FileType
from app.services.geospatial_service import read_geospatial_file, read_shapefile_zip
from tests.fixtures.synthetic_geometries import (
    create_synthetic_kml,
    create_synthetic_shapefile_zip,
)


def test_read_shapefile_zip_polygon(tmp_path: Path) -> None:
    """Verify reading a Shapefile ZIP archive containing Polygons."""
    zip_path = tmp_path / "parcels.zip"
    create_synthetic_shapefile_zip(zip_path, geometry_type="Polygon", crs="EPSG:4326")

    gdf = read_shapefile_zip(zip_path)

    assert len(gdf) == 2
    assert gdf.crs is not None
    assert "4326" in str(gdf.crs)

    assert all(geom.geom_type == "Polygon" for geom in gdf.geometry)
    assert "name" in gdf.columns
    assert "area_class" in gdf.columns
    assert gdf["name"].tolist() == ["Zone A", "Zone B"]


def test_read_shapefile_zip_linestring(tmp_path: Path) -> None:
    """Verify reading a Shapefile ZIP archive containing LineStrings."""
    zip_path = tmp_path / "routes.zip"
    create_synthetic_shapefile_zip(
        zip_path, geometry_type="LineString", crs="EPSG:4326"
    )

    gdf = read_shapefile_zip(zip_path)

    assert len(gdf) == 2
    assert all(geom.geom_type == "LineString" for geom in gdf.geometry)
    assert "status" in gdf.columns


def test_read_shapefile_zip_point(tmp_path: Path) -> None:
    """Verify reading a Shapefile ZIP archive containing Points."""
    zip_path = tmp_path / "sensors.zip"
    create_synthetic_shapefile_zip(zip_path, geometry_type="Point", crs="EPSG:4326")

    gdf = read_shapefile_zip(zip_path)

    assert len(gdf) == 2
    assert all(geom.geom_type == "Point" for geom in gdf.geometry)
    assert "elevation" in gdf.columns


def test_read_shapefile_zip_without_prj(tmp_path: Path) -> None:
    """Verify reading a Shapefile ZIP without .prj file succeeds with None CRS."""
    zip_path = tmp_path / "unprojected.zip"
    create_synthetic_shapefile_zip(zip_path, geometry_type="Polygon", include_prj=False)

    gdf = read_shapefile_zip(zip_path)

    assert len(gdf) == 2
    assert gdf.crs is None


def test_read_shapefile_zip_not_found(tmp_path: Path) -> None:
    """Verify error when ZIP archive is not on disk."""
    missing_zip = tmp_path / "missing.zip"
    with pytest.raises(FileProcessingError) as exc_info:
        read_shapefile_zip(missing_zip)
    assert "not found on disk" in exc_info.value.message


def test_read_shapefile_zip_missing_components(tmp_path: Path) -> None:
    """Verify incomplete Shapefile archive (.shp only, missing .shx/.dbf) is rejected."""
    bad_zip = tmp_path / "broken.zip"
    with zipfile.ZipFile(bad_zip, "w") as zf:
        zf.writestr("test.shp", "dummy shp bytes")

    with pytest.raises(FileValidationError) as exc_info:
        read_shapefile_zip(bad_zip)
    assert "Missing required component" in exc_info.value.message


def test_read_geospatial_file_dispatcher(tmp_path: Path) -> None:
    """Verify unified dispatcher routes both KML and Shapefile ZIP accurately."""
    kml_path = tmp_path / "sample.kml"
    create_synthetic_kml(
        kml_path, include_point=True, include_line=False, include_polygon=False
    )

    shp_zip_path = tmp_path / "sample.zip"
    create_synthetic_shapefile_zip(shp_zip_path, geometry_type="Point")

    gdf_kml = read_geospatial_file(kml_path, FileType.KML)
    assert len(gdf_kml) == 1

    gdf_shp = read_geospatial_file(shp_zip_path, FileType.SHAPEFILE_ZIP)
    assert len(gdf_shp) == 2
