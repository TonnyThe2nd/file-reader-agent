import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.database import get_db
from app.core.security import _requests
from app.main import app
from app.models import Base


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch):
    monkeypatch.setattr(settings, "api_tokens", {})
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "rate_limit_per_minute", 1000)
    _requests.clear()
    yield
    _requests.clear()


@pytest.fixture
def database():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    yield factory
    engine.dispose()


@pytest.fixture
def client(database):
    def override_db():
        with database() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_db, None)
