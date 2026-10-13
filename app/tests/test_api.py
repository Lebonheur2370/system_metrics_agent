import pytest
from fastapi.testclient import TestClient

from app import api

client = TestClient(api.app)

VALID_PAYLOAD = {
    "agent": "system-metrics-agent",
    "event_type": "system_metrics",
    "data": {"cpu": {"percent": 12.5}},
}


@pytest.fixture(autouse=True)
def clear_metrics():
    """Vide le stockage en mémoire avant et après chaque test."""
    api.received_metrics.clear()
    yield
    api.received_metrics.clear()


def test_health():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_latest_returns_404_when_empty():
    response = client.get("/metrics/latest")

    assert response.status_code == 404
    assert response.json()["detail"] == "Aucune métrique disponible."


def test_post_metrics_then_get_latest():
    post = client.post("/metrics", json=VALID_PAYLOAD)

    assert post.status_code == 201
    assert post.json()["total_received"] == 1

    latest = client.get("/metrics/latest")

    assert latest.status_code == 200
    body = latest.json()
    assert body["agent"] == "system-metrics-agent"
    assert body["data"]["cpu"]["percent"] == 12.5
    assert "received_at" in body


def test_get_all_metrics():
    client.post("/metrics", json=VALID_PAYLOAD)
    client.post("/metrics", json=VALID_PAYLOAD)

    response = client.get("/metrics")

    assert response.status_code == 200
    assert response.json()["total"] == 2


def test_post_invalid_payload_is_rejected():
    response = client.post("/metrics", json={"agent": "", "data": {}})

    assert response.status_code == 422