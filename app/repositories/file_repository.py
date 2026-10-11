import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import FeatureModel, FileModel, FileStatus


class FileRepository:
    """Repository handling database operations for files and features."""

    def __init__(self, db: Session):
        self.db = db

    def create_file(
        self,
        original_filename: str,
        stored_filename: str,
        file_type: str,
        file_size_bytes: int,
        file_id: uuid.UUID | None = None,
    ) -> FileModel:
        """Create and persist an initial FileModel record in UPLOADED status."""
        file_record = FileModel(
            id=file_id or uuid.uuid4(),
            original_filename=original_filename,
            stored_filename=stored_filename,
            file_type=file_type,
            file_size_bytes=file_size_bytes,
            status=FileStatus.UPLOADED.value,
        )
        self.db.add(file_record)
        self.db.commit()
        self.db.refresh(file_record)
        return file_record

    def get_file_by_id(self, file_id: uuid.UUID) -> FileModel | None:
        """Retrieve a FileModel by UUID primary key."""
        stmt = select(FileModel).where(FileModel.id == file_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def update_file_status(
        self,
        file_id: uuid.UUID,
        status: FileStatus,
        error_message: str | None = None,
        crs: str | None = None,
        total_features: int | None = None,
        successful_measurements: int | None = None,
        failed_measurements: int | None = None,
        unsupported_features: int | None = None,
    ) -> FileModel | None:
        """Update file processing status and metric counters."""
        file_record = self.get_file_by_id(file_id)
        if not file_record:
            return None

        file_record.status = status.value
        if error_message is not None:
            file_record.error_message = error_message
        if crs is not None:
            file_record.crs = crs
        if total_features is not None:
            file_record.total_features = total_features
        if successful_measurements is not None:
            file_record.successful_measurements = successful_measurements
        if failed_measurements is not None:
            file_record.failed_measurements = failed_measurements
        if unsupported_features is not None:
            file_record.unsupported_features = unsupported_features

        self.db.commit()
        self.db.refresh(file_record)
        return file_record

    def bulk_create_features(self, features: list[FeatureModel]) -> None:
        """Persist a list of FeatureModel records efficiently."""
        if not features:
            return
        self.db.add_all(features)
        self.db.commit()

    def get_features_by_file_id(
        self,
        file_id: uuid.UUID,
        offset: int = 0,
        limit: int = 100,
        status_filter: str | None = None,
    ) -> list[FeatureModel]:
        """Retrieve paginated feature records for a given file."""
        stmt = (
            select(FeatureModel)
            .where(FeatureModel.file_id == file_id)
            .order_by(FeatureModel.feature_index)
        )
        if status_filter:
            stmt = stmt.where(FeatureModel.status == status_filter)

        stmt = stmt.offset(offset).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def count_features_by_file_id(
        self,
        file_id: uuid.UUID,
        status_filter: str | None = None,
    ) -> int:
        """Count total feature records for a file, with optional status filtering."""
        stmt = select(func.count(FeatureModel.id)).where(FeatureModel.file_id == file_id)
        if status_filter:
            stmt = stmt.where(FeatureModel.status == status_filter)
        return int(self.db.execute(stmt).scalar() or 0)
