from pathlib import Path
import uuid
from typing import Tuple

from app.core.config import get_settings
from app.core.exceptions import FileValidationError
from app.db.models import FileType


def validate_file_extension(filename: str) -> str:
    """Validate that the file extension is allowed.

    Returns the normalized lowercase extension (including leading dot).
    Raises FileValidationError if the extension is not supported.
    """
    if not filename or "." not in filename:
        raise FileValidationError(
            message="Uploaded file has no extension.",
            details={"filename": filename},
        )

    ext = Path(filename).suffix.lower()
    settings = get_settings()

    if ext not in settings.ALLOWED_EXTENSIONS:
        raise FileValidationError(
            message=f"Unsupported file extension '{ext}'. Allowed extensions: {sorted(settings.ALLOWED_EXTENSIONS)}",
            details={
                "filename": filename,
                "extension": ext,
                "allowed": list(settings.ALLOWED_EXTENSIONS),
            },
        )

    return ext


def validate_file_size(size_bytes: int) -> None:
    """Validate file size constraints (non-empty and within maximum threshold).

    Raises FileValidationError if file is empty or exceeds limit.
    """
    if size_bytes <= 0:
        raise FileValidationError(
            message="Uploaded file is empty (0 bytes).",
            details={"size_bytes": size_bytes},
        )

    settings = get_settings()
    if size_bytes > settings.MAX_UPLOAD_SIZE_BYTES:
        max_mb = settings.MAX_UPLOAD_SIZE_BYTES / (1024 * 1024)
        actual_mb = size_bytes / (1024 * 1024)
        raise FileValidationError(
            message=f"File size ({actual_mb:.2f} MB) exceeds maximum allowed limit of {max_mb:.2f} MB.",
            details={
                "size_bytes": size_bytes,
                "max_bytes": settings.MAX_UPLOAD_SIZE_BYTES,
            },
        )


def determine_file_type(extension: str) -> FileType:
    """Map validated extension to internal FileType enum."""
    if extension == ".kml":
        return FileType.KML
    if extension == ".zip":
        return FileType.SHAPEFILE_ZIP

    raise FileValidationError(
        message=f"Cannot determine geospatial file type for extension '{extension}'.",
        details={"extension": extension},
    )


def generate_safe_stored_filename(extension: str) -> Tuple[uuid.UUID, str]:
    """Generate a unique UUID and safe filesystem filename.

    Ensures client-provided filenames never touch the local filesystem.
    """
    file_id = uuid.uuid4()
    stored_filename = f"{file_id}{extension}"
    return file_id, stored_filename
