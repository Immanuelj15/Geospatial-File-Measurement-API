import io
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from tests.fixtures.synthetic_geometries import (
    create_synthetic_kml,
    create_synthetic_shapefile_zip,
)


def test_api_upload_kml_success(client: TestClient, tmp_path: Path) -> None:
    """Verify POST /api/files/ uploads, processes, and returns 201 Created for KML."""
    kml_file = tmp_path / "survey.kml"
    create_synthetic_kml(kml_file, include_point=True, include_line=True, include_polygon=True)

    with open(kml_file, "rb") as f:
        response = client.post(
            "/api/files/",
            files={"file": ("survey.kml", f, "application/vnd.google-earth.kml+xml")},
        )

    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["filename"] == "survey.kml"
    assert data["file_type"] == "kml"
    assert data["status"] == "COMPLETED"
    assert data["feature_count"] == 3
    assert data["successful_measurements"] == 3
    assert data["failed_measurements"] == 0
    assert data["unsupported_features"] == 0
    assert "4326" in data["crs"]


def test_api_upload_shapefile_zip_success(client: TestClient, tmp_path: Path) -> None:
    """Verify POST /api/files/ uploads, processes, and returns 201 Created for Shapefile ZIP."""
    zip_file = tmp_path / "parcels.zip"
    create_synthetic_shapefile_zip(zip_file, geometry_type="Polygon")

    with open(zip_file, "rb") as f:
        response = client.post(
            "/api/files/",
            files={"file": ("parcels.zip", f, "application/zip")},
        )

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "COMPLETED"
    assert data["feature_count"] == 2
    assert data["successful_measurements"] == 2


def test_api_get_file_metadata_success(client: TestClient, tmp_path: Path) -> None:
    """Verify GET /api/files/{id}/ returns 200 OK and accurate metadata."""
    kml_file = tmp_path / "test.kml"
    create_synthetic_kml(kml_file, include_point=True, include_line=False, include_polygon=False)

    with open(kml_file, "rb") as f:
        post_resp = client.post(
            "/api/files/",
            files={"file": ("test.kml", f, "application/vnd.google-earth.kml+xml")},
        )
    assert post_resp.status_code == 201
    file_id = post_resp.json()["id"]

    get_resp = client.get(f"/api/files/{file_id}/")
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["id"] == file_id
    assert data["filename"] == "test.kml"
    assert data["status"] == "COMPLETED"
    assert data["feature_count"] == 1


def test_api_get_file_metadata_not_found(client: TestClient) -> None:
    """Verify GET /api/files/{id}/ returns 404 for a non-existent UUID."""
    random_id = uuid.uuid4()
    response = client.get(f"/api/files/{random_id}/")

    assert response.status_code == 404
    data = response.json()
    assert data["error"] == "EntityNotFoundError"
    assert str(random_id) in data["message"]


def test_api_upload_disallowed_extension(client: TestClient) -> None:
    """Verify POST /api/files/ rejects unauthorized file extensions with 400 Bad Request."""
    fake_payload = io.BytesIO(b"print('hello')")
    response = client.post(
        "/api/files/",
        files={"file": ("script.py", fake_payload, "text/x-python")},
    )

    assert response.status_code == 400
    data = response.json()
    assert data["error"] == "FileValidationError"
    assert "Unsupported file extension" in data["message"]


def test_api_upload_empty_file(client: TestClient) -> None:
    """Verify POST /api/files/ rejects 0-byte uploads with 400 Bad Request."""
    empty_payload = io.BytesIO(b"")
    response = client.post(
        "/api/files/",
        files={"file": ("empty.kml", empty_payload, "application/vnd.google-earth.kml+xml")},
    )

    assert response.status_code == 400
    data = response.json()
    assert data["error"] == "FileValidationError"
    assert "empty" in data["message"].lower()
