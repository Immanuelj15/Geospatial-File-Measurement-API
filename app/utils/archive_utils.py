import os
from pathlib import Path
from typing import List, Set
import zipfile

from app.core.exceptions import FileValidationError

REQUIRED_SHAPEFILE_EXTENSIONS: Set[str] = {".shp", ".shx", ".dbf"}
RECOMMENDED_SHAPEFILE_EXTENSIONS: Set[str] = {".prj"}


def safe_extract_zip(zip_path: Path, destination_dir: Path) -> None:
    """Extract a ZIP archive while strictly preventing Zip Slip / path traversal attacks.

    Raises FileValidationError if any file attempts directory traversal.
    """
    destination_dir = destination_dir.resolve()

    try:
        with zipfile.ZipFile(zip_path, "r") as archive:
            for member in archive.infolist():
                # Normalize path and check against destination directory
                normalized_path = os.path.normpath(member.filename)
                if normalized_path.startswith("..") or os.path.isabs(normalized_path):
                    raise FileValidationError(
                        message=f"Archive contains unsafe path: '{member.filename}'. Zip Slip detected.",
                        details={"suspicious_path": member.filename},
                    )

                target_path = (destination_dir / normalized_path).resolve()
                if not str(target_path).startswith(str(destination_dir)):
                    raise FileValidationError(
                        message=f"Archive entry '{member.filename}' escapes target extraction directory.",
                        details={
                            "target_path": str(target_path),
                            "destination_dir": str(destination_dir),
                        },
                    )

            # All members are validated safe: perform extraction
            archive.extractall(destination_dir)

    except zipfile.BadZipFile as exc:
        raise FileValidationError(
            message="The uploaded file is not a valid or readable ZIP archive.",
            details={"error": str(exc)},
        ) from exc


def inspect_shapefile_components(extracted_dir: Path) -> Path:
    """Inspect extracted directory to locate and validate Shapefile components.

    Ensures that for every .shp file found, the required companion files (.shx, .dbf)
    exist. Returns the path to the primary .shp file.
    """
    extracted_dir = extracted_dir.resolve()

    # Search for all .shp files recursively
    shp_files: List[Path] = [
        p
        for p in extracted_dir.rglob("*")
        if p.is_file() and p.suffix.lower() == ".shp"
    ]

    if not shp_files:
        raise FileValidationError(
            message="ZIP archive does not contain a valid Shapefile (.shp file not found).",
            details={"extracted_directory": str(extracted_dir)},
        )

    # Use the first Shapefile found (standard in single-layer archives)
    primary_shp = shp_files[0]
    shp_stem = primary_shp.stem
    parent_dir = primary_shp.parent

    # Check companion files with matching stem
    existing_extensions = {
        p.suffix.lower()
        for p in parent_dir.iterdir()
        if p.stem.lower() == shp_stem.lower()
    }

    missing_required = REQUIRED_SHAPEFILE_EXTENSIONS - existing_extensions
    if missing_required:
        raise FileValidationError(
            message=(
                f"Shapefile '{primary_shp.name}' is incomplete. "
                f"Missing required component file(s): {sorted(missing_required)}. "
                "Shapefiles require .shp, .shx, and .dbf files."
            ),
            details={
                "shp_file": primary_shp.name,
                "missing_extensions": sorted(missing_required),
                "found_extensions": sorted(existing_extensions),
            },
        )

    return primary_shp


def validate_and_extract_shapefile_archive(
    zip_path: Path, extraction_dir: Path
) -> Path:
    """Safely extract ZIP archive and return path to validated .shp file."""
    safe_extract_zip(zip_path, extraction_dir)
    return inspect_shapefile_components(extraction_dir)
