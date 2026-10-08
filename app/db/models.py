from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from sqlalchemy import (
    BigInteger,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class FileStatus(str, Enum):
    """File processing state machine enum."""

    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class FileType(str, Enum):
    """Supported input geospatial file formats."""

    KML = "kml"
    SHAPEFILE_ZIP = "shapefile_zip"


class MeasurementType(str, Enum):
    """Types of vector geometry measurements."""

    AREA = "area"
    LENGTH = "length"


class FeatureStatus(str, Enum):
    """Processing status for an individual vector feature."""

    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    UNSUPPORTED = "UNSUPPORTED"


class FileModel(Base):
    """Relational table tracking uploaded geospatial files and job status."""

    __tablename__ = "files"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_filename: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True
    )
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    crs: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=FileStatus.UPLOADED.value,
        index=True,
    )
    total_features: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    successful_measurements: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    failed_measurements: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unsupported_features: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    features: Mapped[List["FeatureModel"]] = relationship(
        "FeatureModel",
        back_populates="file",
        cascade="all, delete-orphan",
        order_by="FeatureModel.feature_index",
    )


class FeatureModel(Base):
    """Relational table storing individual features, properties, and measurements."""

    __tablename__ = "features"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    file_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("files.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    feature_index: Mapped[int] = mapped_column(Integer, nullable=False)
    geometry_type: Mapped[str] = mapped_column(String(50), nullable=False)
    geometry_geojson: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, nullable=True
    )
    properties: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    measurement_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    measurement_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    measurement_unit: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=FeatureStatus.SUCCESS.value,
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    file: Mapped["FileModel"] = relationship("FileModel", back_populates="features")

    __table_args__ = (
        UniqueConstraint("file_id", "feature_index", name="uq_file_feature_index"),
    )
