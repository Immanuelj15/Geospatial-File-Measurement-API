import io
from pathlib import Path
import zipfile
from fastapi.testclient import TestClient

from tests.fixtures.synthetic_geometries import (
    create_synthetic_kml,
    create_synthetic_mixed_kml,
    create_synthetic_shapefile_zip,
)


def test_end_to_end_kml_workflow(client: TestClient, tmp_path: Path) -> None:
    """Simulate a complete user journey for KML ingestion:
    1. Upload multi-feature KML file.
    2. Poll / verify file metadata status and aggregate counts.
    3. Retrieve paginated measurements.
    4. Apply status filters on measurements.
    """
    kml_file = tmp_path / "comprehensive_survey.kml"
    create_synthetic_kml(
        kml_file,
        include_point=True,
        include_line=True,
        include_polygon=True,
    )

    # 1. Upload KML file
    with open(kml_file, "rb") as f:
        upload_resp = client.post(
            "/api/files/",
            files={
                "file": (
                    "comprehensive_survey.kml",
                    f,
                    "application/vnd.google-earth.kml+xml",
                )
            },
        )
    assert upload_resp.status_code == 201
    upload_data = upload_resp.json()
    file_id = upload_data["id"]

    assert upload_data["filename"] == "comprehensive_survey.kml"
    assert upload_data["file_type"] == "kml"
    assert upload_data["status"] == "COMPLETED"
    assert upload_data["feature_count"] == 3
    assert upload_data["successful_measurements"] == 3
    assert upload_data["failed_measurements"] == 0
    assert upload_data["unsupported_features"] == 0
    assert "EPSG" in upload_data["crs"] or "UTM" in upload_data["crs"]
    assert upload_data["created_at"] is not None
    assert upload_data["updated_at"] is not None

    # 2. Query file metadata directly
    meta_resp = client.get(f"/api/files/{file_id}/")
    assert meta_resp.status_code == 200
    meta_data = meta_resp.json()
    assert meta_data["id"] == file_id
    assert meta_data["status"] == "COMPLETED"
    assert meta_data["feature_count"] == 3

    # 3. Fetch all measurements
    meas_resp = client.get(f"/api/files/{file_id}/measurements/")
    assert meas_resp.status_code == 200
    meas_data = meas_resp.json()
    assert meas_data["file_id"] == file_id
    assert meas_data["total"] == 3
    assert len(meas_data["items"]) == 3

    # Check Polygon calculation
    polygon_item = next(
        i for i in meas_data["items"] if i["geometry_type"] == "Polygon"
    )
    assert polygon_item["measurement_type"] == "area"
    assert polygon_item["unit"] == "m2"
    assert polygon_item["measurement_value"] > 0
    assert polygon_item["status"] == "SUCCESS"

    # Check LineString calculation
    line_item = next(
        i for i in meas_data["items"] if i["geometry_type"] == "LineString"
    )
    assert line_item["measurement_type"] == "length"
    assert line_item["unit"] == "m"
    assert line_item["measurement_value"] > 0
    assert line_item["status"] == "SUCCESS"

    # Check Point calculation (passthrough)
    point_item = next(i for i in meas_data["items"] if i["geometry_type"] == "Point")
    assert point_item["measurement_type"] is None
    assert point_item["unit"] is None
    assert point_item["measurement_value"] is None
    assert point_item["status"] == "SUCCESS"

    # 4. Filter measurements by status
    success_filter_resp = client.get(
        f"/api/files/{file_id}/measurements/?status=SUCCESS"
    )
    assert success_filter_resp.status_code == 200
    assert success_filter_resp.json()["total"] == 3

    failed_filter_resp = client.get(
        f"/api/files/{file_id}/measurements/?status=FAILED"
    )
    assert failed_filter_resp.status_code == 200
    assert failed_filter_resp.json()["total"] == 0
    assert len(failed_filter_resp.json()["items"]) == 0


def test_end_to_end_shapefile_workflow(client: TestClient, tmp_path: Path) -> None:
    """Simulate a complete user journey for Shapefile ZIP ingestion:
    1. Upload Shapefile ZIP archive.
    2. Retrieve metadata.
    3. Retrieve measurements.
    """
    zip_path = tmp_path / "land_use.zip"
    create_synthetic_shapefile_zip(zip_path, geometry_type="Polygon")

    with open(zip_path, "rb") as f:
        upload_resp = client.post(
            "/api/files/",
            files={"file": ("land_use.zip", f, "application/zip")},
        )
    assert upload_resp.status_code == 201
    upload_data = upload_resp.json()
    file_id = upload_data["id"]

    assert upload_data["filename"] == "land_use.zip"
    assert upload_data["file_type"] == "shapefile_zip"
    assert upload_data["status"] == "COMPLETED"
    assert upload_data["feature_count"] == 2
    assert upload_data["successful_measurements"] == 2

    # Verify metadata endpoint
    meta_resp = client.get(f"/api/files/{file_id}/")
    assert meta_resp.status_code == 200
    assert meta_resp.json()["id"] == file_id

    # Verify measurements endpoint
    meas_resp = client.get(f"/api/files/{file_id}/measurements/")
    assert meas_resp.status_code == 200
    meas_data = meas_resp.json()
    assert meas_data["total"] == 2
    for item in meas_data["items"]:
        assert item["geometry_type"] == "Polygon"
        assert item["measurement_type"] == "area"
        assert item["unit"] == "m2"
        assert item["measurement_value"] > 0
        assert item["status"] == "SUCCESS"


def test_end_to_end_partial_dataset_workflow(
    client: TestClient, tmp_path: Path
) -> None:
    """Verify end-to-end ingestion of a dataset with unsupported geometries (PARTIAL status)."""
    kml_file = tmp_path / "mixed_partial.kml"
    create_synthetic_mixed_kml(kml_file)

    with open(kml_file, "rb") as f:
        upload_resp = client.post(
            "/api/files/",
            files={
                "file": (
                    "mixed_partial.kml",
                    f,
                    "application/vnd.google-earth.kml+xml",
                )
            },
        )
    assert upload_resp.status_code == 201
    upload_data = upload_resp.json()
    file_id = upload_data["id"]

    assert upload_data["status"] == "PARTIAL"
    assert upload_data["feature_count"] == 3
    assert upload_data["successful_measurements"] == 2
    assert upload_data["unsupported_features"] == 1

    # Verify filtering for UNSUPPORTED items
    unsupported_resp = client.get(
        f"/api/files/{file_id}/measurements/?status=UNSUPPORTED"
    )
    assert unsupported_resp.status_code == 200
    unsupported_data = unsupported_resp.json()
    assert unsupported_data["total"] == 1
    unsupported_item = unsupported_data["items"][0]
    assert unsupported_item["geometry_type"] == "GeometryCollection"
    assert unsupported_item["status"] == "UNSUPPORTED"
    assert unsupported_item["measurement_type"] is None
    assert unsupported_item["measurement_value"] is None
    assert unsupported_item["error"] is not None


def test_end_to_end_failed_pipeline_corrupted_kml(
    client: TestClient, tmp_path: Path
) -> None:
    """Verify corrupted KML payload registers as FAILED and maintains DB traceability."""
    corrupted_content = b"<kml><Document><Placemark><name>Broken</kml>"
    upload_resp = client.post(
        "/api/files/",
        files={
            "file": (
                "corrupted.kml",
                io.BytesIO(corrupted_content),
                "application/vnd.google-earth.kml+xml",
            )
        },
    )
    # The pipeline gracefully marks the record as FAILED and returns 201 with FAILED status
    assert upload_resp.status_code == 201
    upload_data = upload_resp.json()
    file_id = upload_data["id"]

    assert upload_data["status"] == "FAILED"
    assert upload_data["error_message"] is not None

    # Verify metadata reflects FAILED status
    meta_resp = client.get(f"/api/files/{file_id}/")
    assert meta_resp.status_code == 200
    assert meta_resp.json()["status"] == "FAILED"

    # Verify measurements endpoint returns 0 items without error
    meas_resp = client.get(f"/api/files/{file_id}/measurements/")
    assert meas_resp.status_code == 200
    assert meas_resp.json()["total"] == 0
    assert len(meas_resp.json()["items"]) == 0


def test_api_corrupted_zip_archive_pipeline_failure(client: TestClient) -> None:
    """Verify that uploading a corrupted zip archive is tracked in DB as FAILED with error message."""
    fake_zip_bytes = b"This is not a zip file archive."
    response = client.post(
        "/api/files/",
        files={"file": ("fake_archive.zip", io.BytesIO(fake_zip_bytes), "application/zip")},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "FAILED"
    assert "zip" in data["error_message"].lower() or "bad" in data["error_message"].lower()


def test_api_zip_missing_shapefile_components(client: TestClient) -> None:
    """Verify that a ZIP file missing mandatory shapefile components (.dbf, .shx) records as FAILED."""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zf:
        zf.writestr("test.shp", b"dummy shape data")
        # Missing .shx and .dbf
    zip_buffer.seek(0)

    response = client.post(
        "/api/files/",
        files={"file": ("incomplete_shapefile.zip", zip_buffer, "application/zip")},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "FAILED"
    assert "missing" in data["error_message"].lower() or ".shx" in data["error_message"]


def test_api_get_file_invalid_uuid(client: TestClient) -> None:
    """Verify that passing an invalid UUID string produces a 422 Unprocessable Entity."""
    response = client.get("/api/files/not-a-valid-uuid/")
    assert response.status_code == 422


def test_api_health_endpoint(client: TestClient) -> None:
    """Verify GET /health returns status healthy and application metadata."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "project" in data
    assert "environment" in data


def test_api_docs_and_openapi(client: TestClient) -> None:
    """Verify Swagger documentation and OpenAPI schema endpoints are accessible."""
    docs_resp = client.get("/docs")
    assert docs_resp.status_code == 200

    openapi_resp = client.get("/openapi.json")
    assert openapi_resp.status_code == 200
    schema = openapi_resp.json()
    assert "paths" in schema
    assert "/api/files/" in schema["paths"]
    assert "/api/files/{id}/" in schema["paths"]
    assert "/api/files/{id}/measurements/" in schema["paths"]
