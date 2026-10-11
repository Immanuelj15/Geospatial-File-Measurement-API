import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from tests.fixtures.synthetic_geometries import create_synthetic_kml


def test_api_get_measurements_success(client: TestClient, tmp_path: Path) -> None:
    """Verify GET /api/files/{id}/measurements/ returns correct measurements and status."""
    kml_file = tmp_path / "survey_measurements.kml"
    create_synthetic_kml(kml_file, include_point=True, include_line=True, include_polygon=True)

    with open(kml_file, "rb") as f:
        post_resp = client.post(
            "/api/files/",
            files={
                "file": (
                    "survey_measurements.kml",
                    f,
                    "application/vnd.google-earth.kml+xml",
                )
            },
        )
    assert post_resp.status_code == 201
    file_id = post_resp.json()["id"]

    # Fetch measurements
    get_resp = client.get(f"/api/files/{file_id}/measurements/")
    assert get_resp.status_code == 200
    data = get_resp.json()

    assert data["file_id"] == file_id
    assert data["total"] == 3
    assert data["offset"] == 0
    assert data["limit"] == 100
    assert len(data["items"]) == 3

    # Polygon verification
    polygon_items = [i for i in data["items"] if i["geometry_type"] == "Polygon"]
    assert len(polygon_items) == 1
    poly = polygon_items[0]
    assert poly["measurement_type"] == "area"
    assert poly["unit"] == "m2"
    assert poly["measurement_value"] > 0.0
    assert poly["status"] == "SUCCESS"
    assert "coordinates" in poly["geometry"]

    # LineString verification
    line_items = [i for i in data["items"] if i["geometry_type"] == "LineString"]
    assert len(line_items) == 1
    line = line_items[0]
    assert line["measurement_type"] == "length"
    assert line["unit"] == "m"
    assert line["measurement_value"] > 0.0
    assert line["status"] == "SUCCESS"

    # Point verification
    point_items = [i for i in data["items"] if i["geometry_type"] == "Point"]
    assert len(point_items) == 1
    pt = point_items[0]
    assert pt["measurement_type"] is None
    assert pt["measurement_value"] is None
    assert pt["unit"] is None
    assert pt["status"] == "SUCCESS"


def test_api_get_measurements_pagination(client: TestClient, tmp_path: Path) -> None:
    """Verify pagination limit and offset parameters."""
    kml_file = tmp_path / "page_test.kml"
    create_synthetic_kml(kml_file, include_point=True, include_line=True, include_polygon=True)

    with open(kml_file, "rb") as f:
        post_resp = client.post(
            "/api/files/",
            files={"file": ("page_test.kml", f, "application/vnd.google-earth.kml+xml")},
        )
    file_id = post_resp.json()["id"]

    # Page 1: limit 1, offset 0
    page1 = client.get(f"/api/files/{file_id}/measurements/?limit=1&offset=0")
    assert page1.status_code == 200
    data1 = page1.json()
    assert len(data1["items"]) == 1
    assert data1["items"][0]["feature_id"] == 0
    assert data1["total"] == 3

    # Page 2: limit 1, offset 1
    page2 = client.get(f"/api/files/{file_id}/measurements/?limit=1&offset=1")
    assert page2.status_code == 200
    data2 = page2.json()
    assert len(data2["items"]) == 1
    assert data2["items"][0]["feature_id"] == 1


def test_api_get_measurements_file_not_found(client: TestClient) -> None:
    """Verify 404 response when querying measurements for non-existent file."""
    random_id = uuid.uuid4()
    response = client.get(f"/api/files/{random_id}/measurements/")

    assert response.status_code == 404
    data = response.json()
    assert data["error"] == "EntityNotFoundError"


def test_api_get_measurements_invalid_pagination(client: TestClient, tmp_path: Path) -> None:
    """Verify 422 validation error on negative offset or excessive limit."""
    random_id = uuid.uuid4()

    # Negative offset
    resp1 = client.get(f"/api/files/{random_id}/measurements/?offset=-1")
    assert resp1.status_code == 422

    # Limit > 500
    resp2 = client.get(f"/api/files/{random_id}/measurements/?limit=999")
    assert resp2.status_code == 422
