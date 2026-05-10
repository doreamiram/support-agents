"""Shared pytest fixtures."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base, get_db, init_db
from app.main import app


@pytest.fixture(scope="function")
def db_engine():
    """Fresh in-memory SQLite engine, isolated per test function."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    init_db(engine=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(db_engine):
    """SQLAlchemy session bound to the in-memory engine."""
    factory = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    db = factory()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def client(db_engine):
    """
    FastAPI TestClient with get_db overridden to use the in-memory engine.

    The lifespan (config load + file-based init_db) still runs; only the
    per-request DB sessions are redirected to the in-memory database.
    """
    factory = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)

    def override_get_db():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
