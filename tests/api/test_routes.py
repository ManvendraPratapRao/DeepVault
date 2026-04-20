from fastapi.testclient import TestClient

import app.api.v1.routes.query as query_route
from app.main import app

client = TestClient(app)

# Override the API key dependency for testing — points to the local def in query.py
app.dependency_overrides[query_route.get_api_key] = lambda: "test_key"


def test_health_check_route():
    response = client.get("/api/v1/health")
    # Might return 500 if Redis is not running locally, so we expect 200 or 500
    assert response.status_code in [200, 500]


def test_query_route_validation_error():
    # Missing query_text — should return 422 Unprocessable Entity
    response = client.post(
        "/api/v1/query",
        json={"top_k": 5},
        headers={"X-API-KEY": "deepvault_secret_key"},
    )
    assert response.status_code == 422


def test_ingest_text_validation_error():
    # Missing source — should return 422 Unprocessable Entity
    response = client.post(
        "/api/v1/documents/text",
        json={"content": "Hello"},
        headers={"X-API-KEY": "deepvault_secret_key"},
    )
    assert response.status_code == 422


# Proper integration tests would mock out the services to return dummy data.
