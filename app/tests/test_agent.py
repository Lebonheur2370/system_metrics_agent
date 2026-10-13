from unittest.mock import patch

from app.agent import run_once
from app.config import Settings


@patch("app.agent.send_metrics")
@patch("app.agent.collect_system_metrics")
def test_run_once_collects_formats_and_sends(mock_collect, mock_send):
    mock_collect.return_value = {
        "timestamp": "2026-10-13T00:00:00+00:00",
        "hostname": "test-host",
        "cpu": {"percent": 10.0, "logical_cores": 4},
        "memory": {"percent": 50.0},
        "system": {"load_1m": 0.1, "load_5m": 0.2, "load_15m": 0.3},
    }
    mock_send.return_value = {"status_code": 201, "response": {}}
    settings = Settings(
        metrics_endpoint="http://api:8000/metrics",
        collection_interval=5,
        request_timeout=3,
    )

    result = run_once(settings)

    assert result["status_code"] == 201
    sent = mock_send.call_args.kwargs
    assert sent["endpoint"] == "http://api:8000/metrics"
    assert sent["timeout"] == 3
    assert sent["payload"]["agent"] == "system-metrics-agent"
    assert sent["payload"]["data"]["hostname"] == "test-host"