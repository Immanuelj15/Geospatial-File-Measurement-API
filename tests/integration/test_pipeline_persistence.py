from pathlib import Path

from sqlalchemy.orm import Session

from app.db.models import FeatureStatus, FileStatus, FileType, MeasurementType
from app.repositories.file_repository import FileRepository
from app.services.file_service import FileProcessingService
from tests.fixtures.synthetic_geometries import (
    create_malformed_kml,
    create_synthetic_kml,
    create_synthetic_shapefile_zip,
)


def test_process_pipeline_kml_success(tmp_path: Path, db_session: Session) -> None:
    """Verify end-to-end processing of a valid KML file with database persistence."""
    kml_path = tmp_path / "survey_test.kml"
    create_synthetic_kml(kml_path, include_point=True, include_line=True, include_polygon=True)

    repo = FileRepository(db_session)
    file_record = repo.create_file(
        original_filename="survey_test.kml",
        stored_filename=kml_path.name,
        file_type=FileType.KML.value,
        file_size_bytes=kml_path.stat().st_size,
    )

    service = FileProcessingService(db_session)
    result_file = service.process_file_pipeline(
        file_id=file_record.id,
        file_path=kml_path,
        file_type=FileType.KML,
    )

    assert result_file.status == FileStatus.COMPLETED.value
    assert result_file.total_features == 3
    assert result_file.successful_measurements == 3
    assert result_file.failed_measurements == 0
    assert result_file.unsupported_features == 0
    assert result_file.crs is not None

    # Check child features persisted in DB
    features = repo.get_features_by_file_id(file_record.id)
    assert len(features) == 3

    # Check Polygon feature
    polygon_feats = [f for f in features if f.geometry_type == "Polygon"]
    assert len(polygon_feats) == 1
    assert polygon_feats[0].measurement_type == MeasurementType.AREA.value
    assert polygon_feats[0].measurement_value > 0.0
    assert polygon_feats[0].measurement_unit == "m2"
    assert polygon_feats[0].status == FeatureStatus.SUCCESS.value

    # Check LineString feature
    line_feats = [f for f in features if f.geometry_type == "LineString"]
    assert len(line_feats) == 1
    assert line_feats[0].measurement_type == MeasurementType.LENGTH.value
    assert line_feats[0].measurement_value > 0.0
    assert line_feats[0].measurement_unit == "m"

    # Check Point feature
    point_feats = [f for f in features if f.geometry_type == "Point"]
    assert len(point_feats) == 1
    assert point_feats[0].measurement_value is None
    assert point_feats[0].measurement_unit is None


def test_process_pipeline_shapefile_zip_success(tmp_path: Path, db_session: Session) -> None:
    """Verify end-to-end processing of a Shapefile ZIP archive."""
    zip_path = tmp_path / "parcels.zip"
    create_synthetic_shapefile_zip(zip_path, geometry_type="Polygon")

    repo = FileRepository(db_session)
    file_record = repo.create_file(
        original_filename="parcels.zip",
        stored_filename=zip_path.name,
        file_type=FileType.SHAPEFILE_ZIP.value,
        file_size_bytes=zip_path.stat().st_size,
    )

    service = FileProcessingService(db_session)
    result_file = service.process_file_pipeline(
        file_id=file_record.id,
        file_path=zip_path,
        file_type=FileType.SHAPEFILE_ZIP,
    )

    assert result_file.status == FileStatus.COMPLETED.value
    assert result_file.total_features == 2
    assert result_file.successful_measurements == 2

    features = repo.get_features_by_file_id(file_record.id)
    assert len(features) == 2
    assert all(f.measurement_value > 0.0 for f in features)


def test_process_pipeline_partial_status(tmp_path: Path, db_session: Session) -> None:
    """Verify PARTIAL status when dataset contains both valid and unsupported geometries."""
    kml_path = tmp_path / "mixed.kml"
    content = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Placemark>
      <name>Valid Field</name>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>
              77.5900,12.9700,0
              77.5950,12.9700,0
              77.5950,12.9750,0
              77.5900,12.9750,0
              77.5900,12.9700,0
            </coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>
    <Placemark>
      <name>Unsupported Collection</name>
      <MultiGeometry>
        <Point>
          <coordinates>77.5946,12.9716,0</coordinates>
        </Point>
        <LineString>
          <coordinates>
            77.5946,12.9716,0
            77.5956,12.9726,0
          </coordinates>
        </LineString>
      </MultiGeometry>
    </Placemark>
  </Document>
</kml>"""
    kml_path.write_text(content, encoding="utf-8")

    repo = FileRepository(db_session)
    file_record = repo.create_file(
        original_filename="mixed.kml",
        stored_filename=kml_path.name,
        file_type=FileType.KML.value,
        file_size_bytes=kml_path.stat().st_size,
    )

    service = FileProcessingService(db_session)
    result_file = service.process_file_pipeline(
        file_id=file_record.id,
        file_path=kml_path,
        file_type=FileType.KML,
    )

    assert result_file.status == FileStatus.PARTIAL.value
    assert result_file.total_features == 2
    assert result_file.successful_measurements == 1
    assert result_file.unsupported_features == 1

    features = repo.get_features_by_file_id(file_record.id)
    assert len(features) == 2
    assert features[0].status == FeatureStatus.SUCCESS.value
    assert features[1].status == FeatureStatus.UNSUPPORTED.value


def test_process_pipeline_corrupted_file_failed(tmp_path: Path, db_session: Session) -> None:
    """Verify FAILED status and error trace when file is corrupt."""
    bad_kml = tmp_path / "corrupt.kml"
    create_malformed_kml(bad_kml)

    repo = FileRepository(db_session)
    file_record = repo.create_file(
        original_filename="corrupt.kml",
        stored_filename=bad_kml.name,
        file_type=FileType.KML.value,
        file_size_bytes=bad_kml.stat().st_size,
    )

    service = FileProcessingService(db_session)
    result_file = service.process_file_pipeline(
        file_id=file_record.id,
        file_path=bad_kml,
        file_type=FileType.KML,
    )

    assert result_file.status == FileStatus.FAILED.value
    assert result_file.error_message is not None
    assert "Failed to parse" in result_file.error_message
