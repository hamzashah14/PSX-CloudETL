"""Shared test setup. Everything runs offline: SQLite in memory and mocked HTTP.

Every service calls its module `app`, so services are imported by file path under unique names.
"""
import importlib.util
import os
import pathlib

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
