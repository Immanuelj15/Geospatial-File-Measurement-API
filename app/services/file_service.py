import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.exceptions import EntityNotFoundError
from app.core.logging import logger
from app.db.models import FeatureModel, FeatureStatus, FileModel, FileStatus, FileType
from app.repositories.file_repository import FileRepository
from app.services.crs_service import reproject_dataframe_for_measurement
from app.services.geospatial_service import (
    extract_features_from_dataframe,
    read_geospatial_file,
)
from app.services.measurement_service import measure_dataset


class FileProcessingService:
    """Orchestrates end-to-end ingestion, reprojection, measurement, and persistence."""

    def __init__(self, db: Session):
        self.db = db
        self.repository = FileRepository(db)

    def process_file_pipeline(
        self,
        file_id: uuid.UUID,
        file_path: Path,
        file_type: FileType,
    ) -> FileModel:
        """Execute complete ingestion pipeline for a stored file."""
        file_record = self.repository.get_file_by_id(file_id)
        if not file_record:
            raise EntityNotFoundError(f"File with id '{file_id}' not found.")

        # Step 1: Transition status to PROCESSING
        logger.info("Starting processing pipeline for file %s (%s)", file_id, file_path.name)
        self.repository.update_file_status(file_id, status=FileStatus.PROCESSING)

        try:
            # Step 2: Read vector file into GeoDataFrame
            raw_gdf = read_geospatial_file(file_path, file_type)

            # Step 3: Extract and normalize features from raw GeoDataFrame
            extracted_features = extract_features_from_dataframe(raw_gdf)
            total_features = len(extracted_features)

            if total_features == 0:
                updated = self.repository.update_file_status(
                    file_id=file_id,
                    status=FileStatus.FAILED,
                    error_message="Dataset contains 0 valid vector features.",
                    total_features=0,
                )
                return updated or file_record

            # Step 4: Reproject to optimal metric planar CRS
            proj_gdf, detected_crs_str, _ = reproject_dataframe_for_measurement(raw_gdf)

            # Extract projected geometries corresponding to the extracted features
            projected_geoms = [
                proj_gdf.geometry.iloc[i]
                if i < len(proj_gdf) and not proj_gdf.geometry.iloc[i].is_empty
                else None
                for i in range(total_features)
            ]

            # Step 5: Compute measurements
            measurement_results = measure_dataset(extracted_features, projected_geoms)

            # Step 6: Compute aggregate metrics
            successful_count = sum(
                1 for r in measurement_results if r.status == FeatureStatus.SUCCESS.value
            )
            failed_count = sum(
                1 for r in measurement_results if r.status == FeatureStatus.FAILED.value
            )
            unsupported_count = sum(
                1 for r in measurement_results if r.status == FeatureStatus.UNSUPPORTED.value
            )

            # Step 7: Determine final processing status
            if failed_count == 0 and unsupported_count == 0:
                final_status = FileStatus.COMPLETED
            elif successful_count > 0 and (failed_count > 0 or unsupported_count > 0):
                final_status = FileStatus.PARTIAL
            else:
                final_status = FileStatus.FAILED

            # Step 8: Persist feature records
            feature_models = [
                FeatureModel(
                    file_id=file_id,
                    feature_index=r.feature_index,
                    geometry_type=r.geometry_type,
                    geometry_geojson=r.geometry_geojson,
                    properties=r.properties,
                    measurement_type=r.measurement_type,
                    measurement_value=r.measurement_value,
                    measurement_unit=r.unit,
                    status=r.status,
                    error_message=r.error_message,
                )
                for r in measurement_results
            ]
            self.repository.bulk_create_features(feature_models)

            # Step 9: Update file record with final status and statistics
            updated_file = self.repository.update_file_status(
                file_id=file_id,
                status=final_status,
                crs=detected_crs_str,
                total_features=total_features,
                successful_measurements=successful_count,
                failed_measurements=failed_count,
                unsupported_features=unsupported_count,
                error_message=None
                if final_status != FileStatus.FAILED
                else "All features failed or were unsupported.",
            )

            logger.info(
                "Processing completed for file %s. Status: %s (total: %d, success: %d, failed: %d, unsupported: %d)",
                file_id,
                final_status.value,
                total_features,
                successful_count,
                failed_count,
                unsupported_count,
            )
            return updated_file or file_record

        except Exception as exc:
            logger.error(
                "Processing pipeline failed for file %s: %s",
                file_id,
                str(exc),
                exc_info=True,
            )
            updated_file = self.repository.update_file_status(
                file_id=file_id,
                status=FileStatus.FAILED,
                error_message=str(exc),
            )
            return updated_file or file_record
