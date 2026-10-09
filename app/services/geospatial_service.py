from pathlib import Path
from typing import List

import geopandas as gpd
import pandas as pd
import pyogrio

from app.core.exceptions import FileProcessingError
from app.core.logging import logger


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

    except FileProcessingError:
        raise
    except Exception as exc:
        logger.error(
            "Failed to parse KML file '%s': %s", file_path.name, str(exc), exc_info=True
        )
        raise FileProcessingError(
            message=f"Failed to parse KML file '{file_path.name}': {str(exc)}",
            details={"file_name": file_path.name, "error": str(exc)},
        ) from exc
