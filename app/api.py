"""API FastAPI de réception des métriques."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, Response, status
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    generate_latest,
)
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="System Metrics API",
    description="API de réception des métriques envoyées par les agents.",
    version="1.0.0",
)

received_metrics: list[dict[str, Any]] = []

# ---------- Exposition Prometheus ----------
# Registre dédié : on n'expose que les métriques de l'agent.
registry = CollectorRegistry()


def _gauge(name: str, documentation: str) -> Gauge:
    """Crée une jauge étiquetée par hostname dans le registre dédié."""
    return Gauge(name, documentation, ["hostname"], registry=registry)


# (section du payload, clé, jauge)
GAUGES: list[tuple[str, str, Gauge]] = [
    ("cpu", "percent", _gauge("agent_cpu_percent", "Utilisation CPU (%)")),
    ("cpu", "logical_cores", _gauge("agent_cpu_logical_cores", "Cœurs logiques")),
    ("memory", "percent", _gauge("agent_memory_percent", "Mémoire utilisée (%)")),
    ("memory", "used_bytes", _gauge("agent_memory_used_bytes", "Mémoire utilisée")),
    ("memory", "total_bytes", _gauge("agent_memory_total_bytes", "Mémoire totale")),
    ("system", "load_1m", _gauge("agent_load_1m", "Charge sur 1 minute")),
    ("system", "load_5m", _gauge("agent_load_5m", "Charge sur 5 minutes")),
    ("system", "load_15m", _gauge("agent_load_15m", "Charge sur 15 minutes")),
]

METRICS_RECEIVED = Counter(
    "agent_metrics_received",
    "Nombre de métriques reçues",
    ["hostname"],
    registry=registry,
)
LAST_RECEIVED = Gauge(
    "agent_last_received_timestamp_seconds",
    "Horodatage de la dernière métrique reçue",
    ["hostname"],
    registry=registry,
)


def _is_number(value: Any) -> bool:
    """Vrai pour un int ou un float, faux pour None ou un booléen."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def update_prometheus(data: dict[str, Any]) -> None:
    """Met à jour les jauges Prometheus à partir d'une métrique reçue.

    Les valeurs absentes ou nulles (charge système sous Windows) sont ignorées.
    """
    hostname = str(data.get("hostname", "unknown"))

    for section, key, gauge in GAUGES:
        values = data.get(section)
        if isinstance(values, dict) and _is_number(values.get(key)):
            gauge.labels(hostname=hostname).set(values[key])

    METRICS_RECEIVED.labels(hostname=hostname).inc()
    LAST_RECEIVED.labels(hostname=hostname).set_to_current_time()


class MetricsPayload(BaseModel):
    """Payload reçu depuis l'agent."""

    agent: str = Field(..., min_length=1)
    event_type: str
    data: dict[str, Any]


@app.get("/metrics")
def get_metrics() -> dict[str, Any]:
    """Retourne toutes les métriques reçues."""
    return {
        "total": len(received_metrics),
        "metrics": received_metrics,
    }


@app.get("/health")
def health() -> dict[str, str]:
    """Vérifie l'état de l'API."""
    return {"status": "ok"}


@app.post("/metrics", status_code=status.HTTP_201_CREATED)
def receive_metrics(payload: MetricsPayload) -> dict[str, Any]:
    """Reçoit et stocke temporairement les métriques."""
    item = {
        "received_at": datetime.now(timezone.utc).isoformat(),
        **payload.model_dump(),
    }
    received_metrics.append(item)
    update_prometheus(payload.data)

    logger.info(
        "Métriques reçues de %s. Total=%s",
        payload.agent,
        len(received_metrics),
    )

    return {
        "status": "received",
        "message": "Métriques enregistrées avec succès.",
        "total_received": len(received_metrics),
    }


@app.get("/metrics/latest")
def latest_metrics() -> dict[str, Any]:
    """Retourne la dernière métrique reçue."""
    if not received_metrics:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aucune métrique disponible.",
        )

    return received_metrics[-1]


@app.get("/prometheus")
def prometheus_metrics() -> Response:
    """Expose les métriques au format texte de Prometheus."""
    return Response(content=generate_latest(registry), media_type=CONTENT_TYPE_LATEST)