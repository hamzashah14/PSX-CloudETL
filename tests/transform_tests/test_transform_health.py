"""Transform service /health: it only depends on the machine and its own libraries, so it is deterministic."""
from unittest import mock

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(transform_app):
    return TestClient(transform_app.app)


def machine(monkeypatch, memory, cpu):
    monkeypatch.setattr("psutil.virtual_memory", lambda: mock.Mock(percent=memory))
    monkeypatch.setattr("psutil.cpu_percent", lambda interval=None: cpu)


@pytest.mark.parametrize("memory, cpu, expected", [
    (30, 10, "healthy"),
    (85, 10, "degraded"),
    (30, 85, "degraded"),
    (95, 10, "unhealthy"),
    (30, 95, "unhealthy"),
])
def test_health_status_follows_memory_and_cpu(client, monkeypatch, memory, cpu, expected):
    machine(monkeypatch, memory, cpu)

    body = client.get("/health").json()

    assert body["status"] == expected
    assert body["checks"]["data_processing"] == "healthy"  # the self-test really cleans a sample row
    assert body["checks"]["dependencies"] == "healthy"


def test_health_reports_a_broken_cleaning_step_as_unhealthy(client, transform_app, monkeypatch):
    machine(monkeypatch, 30, 10)
    monkeypatch.setattr(transform_app, "clean_and_standardize", lambda data: [])

    body = client.get("/health").json()

    assert body["checks"]["data_processing"] == "unhealthy - processing failed"
    assert body["status"] == "unhealthy"
