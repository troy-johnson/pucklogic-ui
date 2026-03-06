from fastapi.testclient import TestClient


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200


def test_health_body(client: TestClient) -> None:
    data = client.get("/health").json()
    assert data["status"] == "ok"
    assert "environment" in data
