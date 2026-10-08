import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.main import create_app


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    """Provide isolated settings for test runs."""
    return Settings(
        ENVIRONMENT="testing",
        DEBUG=True,
        DATABASE_URL="sqlite:///:memory:",
    )


@pytest.fixture
def client(test_settings: Settings) -> TestClient:
    """Provide FastAPI test client with overridden settings."""
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: test_settings
    with TestClient(app) as test_client:
        yield test_client
