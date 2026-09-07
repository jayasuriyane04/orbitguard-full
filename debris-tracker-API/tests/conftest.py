import os

os.environ.setdefault("DEBRIS_TRACKER_API_KEYS", "test-key")
os.environ.setdefault("ORBITGUARD_DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("ORBITGUARD_ENABLE_JOBS", "false")
os.environ.setdefault("ORBITGUARD_USE_SYNTHETIC_FALLBACK", "true")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.services.ingestion import ingest_synthetic_fallback


@pytest.fixture()
def db_session():
    """Fresh in-memory SQLite DB per test, seeded with the synthetic catalog."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = TestingSessionLocal()
    ingest_synthetic_fallback(session, seed=42)
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def api_key():
    return os.environ["DEBRIS_TRACKER_API_KEYS"]
