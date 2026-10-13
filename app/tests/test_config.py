import pytest

from app.config import Settings


def test_settings_defaults(monkeypatch):
    for name in ("METRICS_ENDPOINT", "COLLECTION_INTERVAL", "REQUEST_TIMEOUT"):
        monkeypatch.delenv(name, raising=False)

    settings = Settings.from_env()

    assert settings.metrics_endpoint == "http://127.0.0.1:8000/metrics"
    assert settings.collection_interval == 5.0
    assert settings.request_timeout == 5.0


def test_settings_from_environment(monkeypatch):
    monkeypatch.setenv("METRICS_ENDPOINT", "http://api:8000/metrics")
    monkeypatch.setenv("COLLECTION_INTERVAL", "10")
    monkeypatch.setenv("REQUEST_TIMEOUT", "2")

    settings = Settings.from_env()

    assert settings.metrics_endpoint == "http://api:8000/metrics"
    assert settings.collection_interval == 10.0
    assert settings.request_timeout == 2.0


@pytest.mark.parametrize("value", ["abc", "0", "-1"])
def test_settings_invalid_interval(monkeypatch, value):
    monkeypatch.setenv("COLLECTION_INTERVAL", value)

    with pytest.raises(ValueError):
        Settings.from_env()