import pytest
from fastapi.testclient import TestClient
from prometheus_client.parser import text_string_to_metric_families

from app import api

client = TestClient(api.app)

PAYLOAD = {
    "agent": "system-metrics-agent",
    "event_type": "system_metrics",
    "data": {
        "hostname": "srv-01",
        "cpu": {"percent": 42.5, "logical_cores": 4},
        "memory": {"percent": 60.0, "used_bytes": 600, "total_bytes": 1000},
        "system": {"load_1m": 0.5, "load_5m": 0.4, "load_15m": 0.3},
    },
}


@pytest.fixture(autouse=True)
def reset_metrics():
    """Repart d'un état vide : stockage JSON et séries Prometheus."""
    api.received_metrics.clear()
    for _, _, gauge in api.GAUGES:
        gauge.clear()
    api.METRICS_RECEIVED.clear()
    api.LAST_RECEIVED.clear()
    yield


def scrape() -> dict[str, float]:
    """Interroge /prometheus et renvoie {nom_de_série: valeur}."""
    response = client.get("/prometheus")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    return {
        sample.name: sample.value
        for family in text_string_to_metric_families(response.text)
        for sample in family.samples
    }


def test_prometheus_endpoint_exposes_received_metrics():
    client.post("/metrics", json=PAYLOAD)

    samples = scrape()

    assert samples["agent_cpu_percent"] == 42.5
    assert samples["agent_cpu_logical_cores"] == 4
    assert samples["agent_memory_percent"] == 60.0
    assert samples["agent_memory_total_bytes"] == 1000
    assert samples["agent_load_1m"] == 0.5
    assert samples["agent_metrics_received_total"] == 1
    assert samples["agent_last_received_timestamp_seconds"] > 0


def test_prometheus_ignores_null_load_values():
    payload = {**PAYLOAD, "data": {**PAYLOAD["data"], "system": {"load_1m": None}}}
    client.post("/metrics", json=payload)

    samples = scrape()

    assert "agent_load_1m" not in samples
    assert samples["agent_cpu_percent"] == 42.5


def test_prometheus_counts_each_metric():
    client.post("/metrics", json=PAYLOAD)
    client.post("/metrics", json=PAYLOAD)

    assert scrape()["agent_metrics_received_total"] == 2


def test_prometheus_uses_hostname_label():
    client.post("/metrics", json=PAYLOAD)

    response = client.get("/prometheus")

    assert 'agent_cpu_percent{hostname="srv-01"} 42.5' in response.text