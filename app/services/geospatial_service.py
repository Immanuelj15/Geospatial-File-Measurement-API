from pathlib import Path
import tempfile
from typing import List

import geopandas as gpd
import pandas as pd
import pyogrio

from app.core.exceptions import FileProcessingError, FileValidationError
from app.core.logging import logger
from app.db.models import FileType
from app.utils.archive_utils import validate_and_extract_shapefile_archive


def read_kml_file(file_path: Path) -> gpd.GeoDataFrame:
    """Read a KML file into a GeoPandas GeoDataFrame.

    Supports multi-folder/multi-layer documents and automatically defaults
    unspecified coordinate reference systems to EPSG:4326 as required by
    the OGC KML 2.2 standard.

    Raises FileProcessingError if the file is invalid, corrupt, or contains no features.
    """
    if not file_path.is_file():
        raise FileProcessingError(
            message=f"File not found on disk: {file_path.name}",
            details={"file_path": str(file_path)},
        )

    try:
        # Discover all layers/folders inside KML
        raw_layers = pyogrio.list_layers(file_path)
        if len(raw_layers) == 0:
            raise FileProcessingError(
                message="KML file contains no valid geospatial features.",
                details={"file_name": file_path.name},
            )

        # raw_layers is typically a 2D numpy array [[layer_name, geom_type], ...]
        layer_names: List[str] = []
        if hasattr(raw_layers[0], "__iter__") and not isinstance(raw_layers[0], str):
            layer_names = [str(item[0]) for item in raw_layers]
        else:
            layer_names = [str(item) for item in raw_layers]

        gdfs: List[gpd.GeoDataFrame] = []

        if layer_names:
            for layer in layer_names:
                try:
                    df = gpd.read_file(file_path, layer=layer, driver="KML")
                    if not df.empty:
                        gdfs.append(df)
                except Exception as layer_exc:
                    logger.warning(
                        "Could not read KML layer '%s': %s", layer, str(layer_exc)
                    )

        # Fallback to direct read if no layers were extracted
        if not gdfs:
            try:
                fallback_df = gpd.read_file(file_path, driver="KML")
                if not fallback_df.empty:
                    gdfs.append(fallback_df)
            except (IndexError, Exception) as fallback_exc:
                raise FileProcessingError(
                    message="KML file contains no valid geospatial features.",
                    details={"file_name": file_path.name, "error": str(fallback_exc)},
                ) from fallback_exc

        if not gdfs:
            raise FileProcessingError(
                message="KML file contains no valid geospatial features.",
                details={"file_name": file_path.name},
            )

        if len(gdfs) == 1:
            combined_gdf = gdfs[0]
        else:
            combined_gdf = gpd.GeoDataFrame(pd.concat(gdfs, ignore_index=True))

        if combined_gdf.empty or len(combined_gdf) == 0:
            raise FileProcessingError(
                message="KML file contains 0 features.",
                details={"file_name": file_path.name},
            )

        # KML 2.2 standard requires WGS84 coordinates (EPSG:4326)
        if combined_gdf.crs is None:
            logger.info(
                "KML file '%s' has no CRS specified; defaulting to EPSG:4326 (OGC KML 2.2).",
                file_path.name,
            )
            combined_gdf.set_crs("EPSG:4326", inplace=True)

        return combined_gdf

    except (FileProcessingError, FileValidationError):
        raise
    except Exception as exc:
        logger.error(
            "Failed to parse KML file '%s': %s", file_path.name, str(exc), exc_info=True
        )
        raise FileProcessingError(
            message=f"Failed to parse KML file '{file_path.name}': {str(exc)}",
            details={"file_name": file_path.name, "error": str(exc)},
        ) from exc


def read_shapefile_zip(zip_path: Path) -> gpd.GeoDataFrame:
    """Safely extract and read a Shapefile ZIP archive into a GeoPandas GeoDataFrame.

    Guarantees sandboxed temporary directory extraction and automated filesystem
    cleanup upon completion or failure.

    Raises FileProcessingError or FileValidationError if the archive cannot be read
    or contains 0 features.
    """
    if not zip_path.is_file():
        raise FileProcessingError(
            message=f"ZIP archive not found on disk: {zip_path.name}",
            details={"zip_path": str(zip_path)},
        )

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir_path = Path(temp_dir)

            # Step 1: Validate and extract shapefile components (Zip Slip defense + .shp/.shx/.dbf check)
            shp_path = validate_and_extract_shapefile_archive(zip_path, temp_dir_path)

            # Step 2: Read vector data with GeoPandas
            gdf = gpd.read_file(shp_path)

            if gdf.empty or len(gdf) == 0:
                raise FileProcessingError(
                    message="Shapefile contains 0 geospatial features.",
                    details={"file_name": zip_path.name},
                )

            # Step 3: Check CRS
            if gdf.crs is None:
                logger.warning(
                    "Shapefile '%s' does not include projection (.prj) metadata.",
                    zip_path.name,
                )

            # Return an in-memory copy detached from temp files
            return gdf.copy()

    except (FileProcessingError, FileValidationError):
        raise
    except Exception as exc:
        logger.error(
            "Failed to process Shapefile archive '%s': %s",
            zip_path.name,
            str(exc),
            exc_info=True,
        )
        raise FileProcessingError(
            message=f"Failed to process Shapefile archive '{zip_path.name}': {str(exc)}",
            details={"file_name": zip_path.name, "error": str(exc)},
        ) from exc


def read_geospatial_file(file_path: Path, file_type: FileType) -> gpd.GeoDataFrame:
    """Unified dispatcher for reading supported geospatial files (KML or Shapefile ZIP)."""
    if file_type == FileType.KML:
        return read_kml_file(file_path)
    if file_type == FileType.SHAPEFILE_ZIP:
        return read_shapefile_zip(file_path)

    raise FileProcessingError(
        message=f"Unsupported file type '{file_type}'.",
        details={"file_type": str(file_type)},
    )
