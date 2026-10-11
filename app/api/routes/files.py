from typing import Optional
import uuid

from fastapi import APIRouter, Depends, File, Query, status, UploadFile
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.exceptions import EntityNotFoundError
from app.core.logging import logger
from app.db.database import get_db
from app.repositories.file_repository import FileRepository
from app.schemas.file import FileDetailResponse
from app.schemas.measurement import PaginatedMeasurementsResponse
from app.services.file_service import FileProcessingService
from app.utils.file_validation import (
    determine_file_type,
    generate_safe_stored_filename,
    validate_file_extension,
    validate_file_size,
)

router = APIRouter(prefix="/files", tags=["Files"])


@router.post(
    "/",
    response_model=FileDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and process a geospatial vector file",
    description="Accepts a .kml file or a .zip archive containing an ESRI Shapefile, validates and ingests it, transforms coordinates to an optimal metric projected CRS, and computes planar measurements.",
)
async def upload_geospatial_file(
    file: UploadFile = File(..., description="Geospatial file (.kml or .zip)"),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> FileDetailResponse:
    """Handle multipart file upload, validate integrity, and trigger the measurement pipeline."""
    client_filename = file.filename or "unnamed_upload"

    # Step 1: Validate file extension
    ext = validate_file_extension(client_filename)
    file_type = determine_file_type(ext)

    # Step 2: Read payload and validate size
    content = await file.read()
    file_size_bytes = len(content)
    validate_file_size(file_size_bytes)

    # Step 3: Generate safe internal storage filename
    file_id, stored_filename = generate_safe_stored_filename(ext)
    dest_path = settings.UPLOAD_DIR / stored_filename

    # Ensure upload directory exists and write bytes
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    dest_path.write_bytes(content)
    logger.info(
        "Saved upload '%s' safely as '%s' (%d bytes)",
        client_filename,
        stored_filename,
        file_size_bytes,
    )

    # Step 4: Register initial FileModel record in DB
    repository = FileRepository(db)
    file_record = repository.create_file(
        original_filename=client_filename,
        stored_filename=stored_filename,
        file_type=file_type.value,
        file_size_bytes=file_size_bytes,
        file_id=file_id,
    )

    # Step 5: Execute processing pipeline
    service = FileProcessingService(db)
    processed_record = service.process_file_pipeline(
        file_id=file_record.id,
        file_path=dest_path,
        file_type=file_type,
    )

    return FileDetailResponse.model_validate(processed_record)


@router.get(
    "/{id}/",
    response_model=FileDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve file metadata and processing status",
    description="Fetch processing status, feature counts, and CRS metadata for a previously uploaded geospatial file by UUID.",
)
def get_file_metadata(
    id: uuid.UUID,
    db: Session = Depends(get_db),
) -> FileDetailResponse:
    """Retrieve file record by ID or return 404 if not found."""
    repository = FileRepository(db)
    file_record = repository.get_file_by_id(id)

    if not file_record:
        raise EntityNotFoundError(
            message=f"Geospatial file with ID '{id}' was not found.",
            details={"file_id": str(id)},
        )

    return FileDetailResponse.model_validate(file_record)


@router.get(
    "/{id}/measurements/",
    response_model=PaginatedMeasurementsResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve paginated feature measurements",
    description="Fetch individual vector feature measurements (area for Polygons, length for LineStrings, null for Points) for a processed geospatial file.",
)
def get_file_measurements(
    id: uuid.UUID,
    offset: int = Query(default=0, ge=0, description="Number of items to skip"),
    limit: int = Query(
        default=100, ge=1, le=500, description="Max items to return (1-500)"
    ),
    status_filter: Optional[str] = Query(
        default=None,
        alias="status",
        description="Filter by feature status (SUCCESS, FAILED, UNSUPPORTED)",
    ),
    db: Session = Depends(get_db),
) -> PaginatedMeasurementsResponse:
    """Retrieve paginated feature measurements for a given file ID."""
    repository = FileRepository(db)
    file_record = repository.get_file_by_id(id)

    if not file_record:
        raise EntityNotFoundError(
            message=f"Geospatial file with ID '{id}' was not found.",
            details={"file_id": str(id)},
        )

    total = repository.count_features_by_file_id(id, status_filter=status_filter)
    features = repository.get_features_by_file_id(
        file_id=id,
        offset=offset,
        limit=limit,
        status_filter=status_filter,
    )

    return PaginatedMeasurementsResponse(
        file_id=id,
        total=total,
        offset=offset,
        limit=limit,
        items=features,
    )
