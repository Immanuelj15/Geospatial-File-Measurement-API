import uuid
import pytest

from app.core.exceptions import FileValidationError
from app.db.models import FileType
from app.utils.file_validation import (
    determine_file_type,
    generate_safe_stored_filename,
    validate_file_extension,
    validate_file_size,
)


def test_validate_file_extension_valid() -> None:
    """Verify valid extensions are accepted and normalized."""
    assert validate_file_extension("survey.kml") == ".kml"
    assert validate_file_extension("SURVEY.KML") == ".kml"
    assert validate_file_extension("parcels.zip") == ".zip"
    assert validate_file_extension("PARCELS.ZIP") == ".zip"


def test_validate_file_extension_invalid() -> None:
    """Verify unsupported extensions raise FileValidationError."""
    with pytest.raises(FileValidationError) as exc_info:
        validate_file_extension("script.py")
    assert "Unsupported file extension" in exc_info.value.message

    with pytest.raises(FileValidationError):
        validate_file_extension("no_extension")

    with pytest.raises(FileValidationError):
        validate_file_extension(".kml")


def test_validate_file_size() -> None:
    """Verify size limits (non-zero and under limit)."""
    # 0 bytes -> error
    with pytest.raises(FileValidationError) as exc_info:
        validate_file_size(0)
    assert "empty" in exc_info.value.message.lower()

    # Negative bytes -> error
    with pytest.raises(FileValidationError):
        validate_file_size(-10)

    # Valid size (e.g. 1 MB) -> pass
    validate_file_size(1024 * 1024)

    # Oversized (e.g. 30 MB when limit is 25 MB) -> error
    with pytest.raises(FileValidationError) as exc_info:
        validate_file_size(30 * 1024 * 1024)
    assert "exceeds maximum allowed limit" in exc_info.value.message


def test_determine_file_type() -> None:
    """Verify mapping from extension to FileType enum."""
    assert determine_file_type(".kml") == FileType.KML
    assert determine_file_type(".zip") == FileType.SHAPEFILE_ZIP

    with pytest.raises(FileValidationError):
        determine_file_type(".geojson")


def test_generate_safe_stored_filename() -> None:
    """Verify generated filename uses UUID and keeps extension."""
    file_id, stored_name = generate_safe_stored_filename(".kml")
    assert isinstance(file_id, uuid.UUID)
    assert stored_name == f"{file_id}.kml"
    assert ".." not in stored_name
    assert "/" not in stored_name
    assert "\\" not in stored_name
