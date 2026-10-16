"""Load service /health: a working database is healthy, a broken one is reported and answers 503."""
import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from unittest import mock


class Machine:
    def __init__(self, percent):
        self.percent = percent


class Transform:
    """Stands in for httpx.AsyncClient talking to the Transform service."""

    status = 200
    error = None

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, url):
        if Transform.error:
            raise Transform.error
        return mock.Mock(status_code=Transform.status)


@pytest.fixture(autouse=True)
def calm_machine_and_transform(monkeypatch):
    monkeypatch.setattr("psutil.virtual_memory", lambda: Machine(20))
    monkeypatch.setattr("psutil.cpu_percent", lambda interval=None: 10)
    monkeypatch.setattr("psutil.disk_usage", lambda path: Machine(30))
    monkeypatch.setattr(httpx, "AsyncClient", Transform)
    Transform.status, Transform.error = 200, None


@pytest.fixture()
def sessions():
    """Counts the sessions the health check opens and closes."""
    return {"opened": 0, "closed": 0}


def use_database(monkeypatch, load_app, engine, sessions):
    class CountingSession(Session):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            sessions["opened"] += 1

        def close(self):
            sessions["closed"] += 1
            return super().close()

    monkeypatch.setattr(load_app, "engine", engine)
    monkeypatch.setattr(load_app, "SessionLocal", sessionmaker(bind=engine, class_=CountingSession))


@pytest.fixture()
def database_with_schema(monkeypatch, load_app, sessions):
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    load_app.Base.metadata.create_all(engine)
    use_database(monkeypatch, load_app, engine, sessions)


@pytest.fixture()
def client(load_app):
    return TestClient(load_app.app)


def test_health_is_healthy_when_the_database_and_transform_service_work(client, database_with_schema, sessions):
    response = client.get("/health")

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "healthy"
    assert body["checks"]["database"] == "healthy"
    assert body["checks"]["database_schema"] == "healthy"
    assert body["checks"]["data_loading"] == "healthy"
    assert sessions["opened"] == sessions["closed"] > 0


def test_health_answers_503_when_the_database_is_unreachable(monkeypatch, load_app, client, sessions):
    unreachable = create_engine("sqlite:////no/such/folder/warehouse.db")
    use_database(monkeypatch, load_app, unreachable, sessions)

    response = client.get("/health")

    body = response.json()
    assert response.status_code == 503
    assert body["status"] == "unhealthy"
    assert body["checks"]["database"].startswith("unhealthy")
    assert sessions["opened"] == sessions["closed"]  # failed checks must not leak connections


def test_health_answers_503_when_the_tables_are_missing(monkeypatch, load_app, client, sessions):
    empty = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    use_database(monkeypatch, load_app, empty, sessions)

    response = client.get("/health")

    body = response.json()
    assert response.status_code == 503
    assert body["checks"]["database"] == "healthy"  # the server answers, the warehouse is just empty
    assert "missing tables" in body["checks"]["database_schema"]
    for table in ("fact_stock_prices", "dim_ticker", "dim_date", "dim_time"):
        assert table in body["checks"]["database_schema"]


@pytest.mark.parametrize("failure", [httpx.ConnectError("transform-service: name not resolved"), None])
def test_a_transform_outage_does_not_fail_the_loads_own_health_check(client, database_with_schema, failure):
    # The pod is probed on /health. Restarting Load will not fix Transform, so only Load's own
    # dependency (the database) turns the HTTP status into 503.
    Transform.error = failure
    Transform.status = 500 if failure is None else 200

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["checks"]["transform_service"].split(" ")[0] in {"unhealthy", "degraded"}
