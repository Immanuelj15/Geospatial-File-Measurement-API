from fastapi.testclient import TestClient

from app.core.config import Settings


def test_settings_initialization() -> None:
    """Verify settings initialize with expected defaults."""
    settings = Settings(PROJECT_NAME="Test Suite API", ENVIRONMENT="testing")
    assert settings.PROJECT_NAME == "Test Suite API"
    assert settings.ENVIRONMENT == "testing"
    assert settings.MAX_UPLOAD_SIZE_BYTES == 25 * 1024 * 1024
    assert ".kml" in settings.ALLOWED_EXTENSIONS
    assert ".zip" in settings.ALLOWED_EXTENSIONS


def test_health_check_endpoint(client: TestClient) -> None:
    """Verify GET /health returns 200 and healthy status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["environment"] == "testing"
    assert "project" in data
