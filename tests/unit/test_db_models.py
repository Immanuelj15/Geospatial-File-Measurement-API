import uuid
import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import (
    FeatureModel,
    FeatureStatus,
    FileModel,
    FileStatus,
    FileType,
    MeasurementType,
)


def test_create_file_model(db_session: Session) -> None:
    """Verify FileModel persistence and default fields."""
    file_record = FileModel(
        original_filename="survey_2026.kml",
        stored_filename=f"{uuid.uuid4()}.kml",
        file_type=FileType.KML.value,
        file_size_bytes=1048576,
        crs="EPSG:4326",
        status=FileStatus.UPLOADED.value,
    )
    db_session.add(file_record)
    db_session.commit()
    db_session.refresh(file_record)

    assert isinstance(file_record.id, uuid.UUID)
    assert file_record.original_filename == "survey_2026.kml"
    assert file_record.status == FileStatus.UPLOADED.value
    assert file_record.total_features == 0
    assert file_record.created_at is not None
    assert file_record.updated_at is not None


def test_create_file_with_features_and_cascade_delete(db_session: Session) -> None:
    """Verify parent-child relationship and cascade delete."""
    file_record = FileModel(
        original_filename="parcels.zip",
        stored_filename=f"{uuid.uuid4()}.zip",
        file_type=FileType.SHAPEFILE_ZIP.value,
        file_size_bytes=204800,
        crs="EPSG:32643",
        status=FileStatus.PROCESSING.value,
    )
    db_session.add(file_record)
    db_session.commit()

    feature1 = FeatureModel(
        file_id=file_record.id,
        feature_index=0,
        geometry_type="Polygon",
        geometry_geojson={
            "type": "Polygon",
            "coordinates": [[[0, 0], [0, 1], [1, 1], [0, 0]]],
        },
        properties={"parcel_id": "P-101"},
        measurement_type=MeasurementType.AREA.value,
        measurement_value=12500.5,
        measurement_unit="m2",
        status=FeatureStatus.SUCCESS.value,
    )
    feature2 = FeatureModel(
        file_id=file_record.id,
        feature_index=1,
        geometry_type="Point",
        geometry_geojson={"type": "Point", "coordinates": [0.5, 0.5]},
        properties={"name": "Boundary Marker"},
        measurement_type=None,
        measurement_value=None,
        measurement_unit=None,
        status=FeatureStatus.SUCCESS.value,
    )
    db_session.add_all([feature1, feature2])
    db_session.commit()

    # Verify features are retrievable through relationship
    db_session.refresh(file_record)
    assert len(file_record.features) == 2
    assert file_record.features[0].feature_index == 0
    assert file_record.features[0].measurement_value == 12500.5
    assert file_record.features[1].measurement_value is None

    # Test cascade delete: removing the file must delete all features
    db_session.delete(file_record)
    db_session.commit()

    remaining_features = (
        db_session.query(FeatureModel).filter_by(file_id=file_record.id).all()
    )
    assert len(remaining_features) == 0


def test_unique_constraint_file_and_feature_index(db_session: Session) -> None:
    """Verify unique constraint on (file_id, feature_index)."""
    file_record = FileModel(
        original_filename="boundary.kml",
        stored_filename=f"{uuid.uuid4()}.kml",
        file_type=FileType.KML.value,
        file_size_bytes=5000,
    )
    db_session.add(file_record)
    db_session.commit()

    feature1 = FeatureModel(
        file_id=file_record.id,
        feature_index=0,
        geometry_type="LineString",
    )
    db_session.add(feature1)
    db_session.commit()

    # Attempt to insert duplicate feature_index for same file
    feature_duplicate = FeatureModel(
        file_id=file_record.id,
        feature_index=0,
        geometry_type="LineString",
    )
    db_session.add(feature_duplicate)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
