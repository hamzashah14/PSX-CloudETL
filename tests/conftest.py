"""Shared test setup. Everything runs offline: SQLite in memory and mocked HTTP.

Every service calls its module `app`, so services are imported by file path under unique names.
"""
import importlib.util
import os
import pathlib
import socket
from unittest import mock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# The load service connects to its database when imported. Force in-memory SQLite so a DATABASE_URL
# set in the shell or in .env can never make the tests touch a real database.
os.environ["DATABASE_URL"] = "sqlite://"

ROOT = pathlib.Path(__file__).resolve().parents[1]


def import_service(name):
    spec = importlib.util.spec_from_file_location(f"{name}_service_app", ROOT / "services" / name / "app.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True, scope="session")
def no_network():
    """Fail any test that tries to open a real connection or resolve a name."""
    def blocked(*args, **kwargs):
        raise RuntimeError("tests must not use the network")

    with pytest.MonkeyPatch.context() as mp:
        for name in ("getaddrinfo", "create_connection"):
            mp.setattr(socket, name, blocked)
        mp.setattr(socket.socket, "connect", blocked)
        mp.setattr(socket.socket, "connect_ex", blocked)
        yield


@pytest.fixture(scope="session")
def extract_app():
    return import_service("extract")


@pytest.fixture(scope="session")
def scheduler_app():
    # The scheduler starts its background loop when imported. Stub the thread so no loop runs in tests.
    with mock.patch("threading.Thread"):
        return import_service("scheduler")


@pytest.fixture()
def import_scheduler():
    """Import the scheduler again (to test configuration read at import time), still without its thread."""
    def load():
        with mock.patch("threading.Thread"):
            return import_service("scheduler")
    return load


@pytest.fixture(scope="session")
def visualization_app():
    return import_service("visualization")


@pytest.fixture(scope="session")
def load_app():
    return import_service("load")


@pytest.fixture(scope="session")
def transform_app():
    return import_service("transform")


@pytest.fixture()
def db(load_app):
    """Fresh star-schema tables in a throwaway in-memory SQLite database."""
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    load_app.Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
