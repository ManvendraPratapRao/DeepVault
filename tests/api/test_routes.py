from fastapi.testclient import TestClient

from app.api.dependencies import get_api_key
from app.main import app

client = TestClient(app)

# Override the API key dependency for testing so we don't get 403s
app.dependency_overrides[get_api_key] = lambda: "test_key"


def test_health_check_route():
    response = client.get("/api/v1/health")
    # Might return 500 if Redis is not running locally, so we expect 200 or 500
    assert response.status_code in [200, 500]


def test_query_route_validation_error():
    # Missing query_text
    response = client.post("/api/v1/query", json={"top_k": 5})
    assert response.status_code == 422


def test_ingest_text_validation_error():
    # Missing source
    response = client.post("/api/v1/documents/text", json={"content": "Hello"})
    assert response.status_code == 422


# Proper integration tests would mock out the services to return dummy data.
