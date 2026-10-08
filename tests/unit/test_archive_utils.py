import zipfile
from pathlib import Path
import pytest

from app.core.exceptions import FileValidationError
from app.utils.archive_utils import (
    inspect_shapefile_components,
    safe_extract_zip,
    validate_and_extract_shapefile_archive,
)


def test_safe_extract_zip_valid(tmp_path: Path) -> None:
    """Verify safe extraction of standard zip archive."""
    zip_path = tmp_path / "valid.zip"
    extract_dir = tmp_path / "extracted"
    extract_dir.mkdir()

    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("test.txt", "sample content")
        zf.writestr("subfolder/data.txt", "nested content")

    safe_extract_zip(zip_path, extract_dir)

    assert (extract_dir / "test.txt").exists()
    assert (extract_dir / "subfolder" / "data.txt").exists()
    assert (extract_dir / "test.txt").read_text() == "sample content"


def test_safe_extract_zip_slip_rejected(tmp_path: Path) -> None:
    """Verify malicious archive attempting directory traversal is rejected."""
    zip_path = tmp_path / "malicious.zip"
    extract_dir = tmp_path / "extracted"
    extract_dir.mkdir()

    with zipfile.ZipFile(zip_path, "w") as zf:
        # Write member with relative path traversal
        zf.writestr("../evil.txt", "malicious payload")

    with pytest.raises(FileValidationError) as exc_info:
        safe_extract_zip(zip_path, extract_dir)
    assert "Zip Slip detected" in exc_info.value.message


def test_safe_extract_corrupt_zip(tmp_path: Path) -> None:
    """Verify corrupted zip archive raises FileValidationError."""
    corrupt_zip = tmp_path / "corrupt.zip"
    corrupt_zip.write_bytes(b"not a real zip content")
    extract_dir = tmp_path / "extracted"
    extract_dir.mkdir()

    with pytest.raises(FileValidationError) as exc_info:
        safe_extract_zip(corrupt_zip, extract_dir)
    assert "not a valid or readable ZIP archive" in exc_info.value.message


def test_inspect_shapefile_components_valid(tmp_path: Path) -> None:
    """Verify Shapefile with all required companion files is detected."""
    shp_dir = tmp_path / "shapefile_data"
    shp_dir.mkdir()

    (shp_dir / "boundaries.shp").touch()
    (shp_dir / "boundaries.shx").touch()
    (shp_dir / "boundaries.dbf").touch()
    (shp_dir / "boundaries.prj").touch()

    shp_path = inspect_shapefile_components(shp_dir)
    assert shp_path.name == "boundaries.shp"
    assert shp_path.exists()


def test_inspect_shapefile_missing_components(tmp_path: Path) -> None:
    """Verify missing .shx or .dbf raises FileValidationError."""
    shp_dir = tmp_path / "incomplete_data"
    shp_dir.mkdir()

    # Missing .shx and .dbf
    (shp_dir / "boundaries.shp").touch()

    with pytest.raises(FileValidationError) as exc_info:
        inspect_shapefile_components(shp_dir)
    assert "Missing required component file(s)" in exc_info.value.message
    assert ".shx" in exc_info.value.message
    assert ".dbf" in exc_info.value.message


def test_inspect_shapefile_no_shp_present(tmp_path: Path) -> None:
    """Verify error raised when archive contains no .shp file."""
    empty_dir = tmp_path / "empty_dir"
    empty_dir.mkdir()
    (empty_dir / "readme.txt").touch()

    with pytest.raises(FileValidationError) as exc_info:
        inspect_shapefile_components(empty_dir)
    assert ".shp file not found" in exc_info.value.message


def test_validate_and_extract_shapefile_archive_end_to_end(tmp_path: Path) -> None:
    """Verify end-to-end extraction and inspection of a Shapefile zip."""
    zip_path = tmp_path / "complete_shapefile.zip"
    extract_dir = tmp_path / "extracted"
    extract_dir.mkdir()

    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("parcels.shp", "shp data")
        zf.writestr("parcels.shx", "shx data")
        zf.writestr("parcels.dbf", "dbf data")
        zf.writestr("parcels.prj", "prj data")

    primary_shp = validate_and_extract_shapefile_archive(zip_path, extract_dir)
    assert primary_shp.name == "parcels.shp"
    assert (extract_dir / "parcels.shx").exists()
