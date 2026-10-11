import tempfile
import uuid
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.exceptions import FileValidationError
from app.services.geospatial_service import read_shapefile_zip
from app.utils.archive_utils import safe_extract_zip
from app.utils.file_validation import (
    generate_safe_stored_filename,
    validate_file_extension,
    validate_file_size,
)
from tests.fixtures.synthetic_geometries import create_synthetic_shapefile_zip


def test_security_headers_present_on_responses(client: TestClient) -> None:
    """Verify that all HTTP responses include critical security hardening headers."""
    response = client.get("/health")
    assert response.status_code == 200

    headers = response.headers
    assert headers.get("X-Content-Type-Options") == "nosniff"
    assert headers.get("X-Frame-Options") == "DENY"
    assert headers.get("X-XSS-Protection") == "1; mode=block"
    assert headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"


def test_unified_error_envelope_422_validation_error(client: TestClient) -> None:
    """Verify that FastAPI parameter validation errors conform to standard JSON error envelope."""
    # Pass an invalid UUID to /api/files/{id}/
    response = client.get("/api/files/not-a-valid-uuid/")
    assert response.status_code == 422
    data = response.json()

    assert data["error"] == "ValidationError"
    assert "invalid parameters" in data["message"].lower()
    assert isinstance(data["details"], list)
    assert len(data["details"]) > 0


def test_unified_error_envelope_404_route_not_found(client: TestClient) -> None:
    """Verify that unmapped route requests return standardized HTTP_404 envelope."""
    response = client.get("/api/non-existent-endpoint/")
    assert response.status_code == 404
    data = response.json()

    assert data["error"] == "HTTP_404"
    assert "not found" in data["message"].lower()
    assert "details" in data


def test_unified_error_envelope_405_method_not_allowed(client: TestClient) -> None:
    """Verify that disallowed HTTP methods return standardized HTTP_405 envelope."""
    # GET is not allowed on /api/files/ (only POST is defined)
    response = client.put("/api/files/")
    assert response.status_code == 405
    data = response.json()

    assert data["error"] == "HTTP_405"
    assert "method not allowed" in data["message"].lower()


def test_adversarial_zip_slip_traversal_relative_parent(tmp_path: Path) -> None:
    """Verify that a ZIP entry attempting relative parent path traversal (../) is rejected."""
    malicious_zip = tmp_path / "zip_slip_relative.zip"
    extract_target = tmp_path / "extracted"
    extract_target.mkdir()

    with zipfile.ZipFile(malicious_zip, "w") as zf:
        zf.writestr("../evil_file.txt", b"malicious payload")

    with pytest.raises(FileValidationError) as exc_info:
        safe_extract_zip(malicious_zip, extract_target)

    assert "Zip Slip detected" in exc_info.value.message or "escapes" in exc_info.value.message


def test_adversarial_zip_slip_traversal_nested_escape(tmp_path: Path) -> None:
    """Verify that a nested directory escape (sub/../../evil.txt) is rejected."""
    malicious_zip = tmp_path / "zip_slip_nested.zip"
    extract_target = tmp_path / "extracted_nested"
    extract_target.mkdir()

    with zipfile.ZipFile(malicious_zip, "w") as zf:
        zf.writestr("sub/../../evil_file.txt", b"malicious payload")

    with pytest.raises(FileValidationError) as exc_info:
        safe_extract_zip(malicious_zip, extract_target)

    assert (
        "unsafe path" in exc_info.value.message.lower()
        or "escapes" in exc_info.value.message.lower()
    )


def test_adversarial_filename_injection_sanitization() -> None:
    """Verify that adversarial filenames (path traversal, shell injection) are never used on the filesystem."""
    adversarial_inputs = [
        "../../etc/passwd.kml",
        "..\\..\\windows\\system32\\cmd.kml",
        "; rm -rf /; .kml",
        "nested/path/to/file.kml",
    ]

    for malicious_name in adversarial_inputs:
        ext = validate_file_extension(malicious_name)
        assert ext == ".kml"

        file_id, stored_name = generate_safe_stored_filename(ext)
        # Ensure file_id is a valid RFC-4122 UUID
        assert isinstance(file_id, uuid.UUID)
        # Ensure stored filename consists strictly of UUID and extension, zero path characters
        assert "/" not in stored_name
        assert "\\" not in stored_name
        assert ".." not in stored_name
        assert stored_name == f"{file_id}.kml"


def test_adversarial_file_size_thresholds() -> None:
    """Verify file size bounds defense: 0-byte, negative, and oversized payloads."""
    settings = get_settings()

    # 0 bytes
    with pytest.raises(FileValidationError) as exc1:
        validate_file_size(0)
    assert "empty" in exc1.value.message.lower()

    # Negative bytes
    with pytest.raises(FileValidationError) as exc2:
        validate_file_size(-100)
    assert "empty" in exc2.value.message.lower()

    # Exceeding 25 MB limit
    with pytest.raises(FileValidationError) as exc3:
        validate_file_size(settings.MAX_UPLOAD_SIZE_BYTES + 1)
    assert "exceeds" in exc3.value.message.lower()


def test_shapefile_temp_directory_cleaned_up_on_failure(tmp_path: Path) -> None:
    """Verify that temp directories created during Shapefile extraction are guaranteed to be cleaned up."""
    # Create an invalid zip
    bad_zip = tmp_path / "bad.zip"
    bad_zip.write_bytes(b"not a valid zip file")

    temp_root = Path(tempfile.gettempdir())
    before_dirs = set(temp_root.iterdir())

    with pytest.raises(FileValidationError):
        read_shapefile_zip(bad_zip)

    after_dirs = set(temp_root.iterdir())
    # No temporary directories left leaking
    new_dirs = after_dirs - before_dirs
    assert len([d for d in new_dirs if d.name.startswith("tmp")]) == 0


def test_shapefile_temp_directory_cleaned_up_on_success(tmp_path: Path) -> None:
    """Verify that temp directories created during successful Shapefile reading are cleaned up."""
    valid_zip = tmp_path / "valid.zip"
    create_synthetic_shapefile_zip(valid_zip, geometry_type="Polygon")

    temp_root = Path(tempfile.gettempdir())
    before_dirs = set(temp_root.iterdir())

    gdf = read_shapefile_zip(valid_zip)
    assert len(gdf) == 2

    after_dirs = set(temp_root.iterdir())
    new_dirs = after_dirs - before_dirs
    assert len([d for d in new_dirs if d.name.startswith("tmp")]) == 0
