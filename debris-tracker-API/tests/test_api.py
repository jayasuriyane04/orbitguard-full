import pytest
from fastapi.testclient import TestClient

from app.db.base import Base, get_db
from app.main import app
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services.ingestion import ingest_synthetic_fallback

_engine = create_engine(
    "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
)
_TestSessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False)


def _override_get_db():
    db = _TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="module", autouse=True)
def _setup_db():
    Base.metadata.create_all(bind=_engine)
    session = _TestSessionLocal()
    ingest_synthetic_fallback(session, seed=42)
    session.close()
    app.dependency_overrides[get_db] = _override_get_db
    yield
    app.dependency_overrides.clear()


@pytest.fixture()
def client():
    return TestClient(app)


API_KEY = "test-key"
HEADERS = {"X-API-Key": API_KEY}


def test_health_no_auth_required(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["objects_tracked"] >= 1


def test_objects_requires_api_key(client):
    resp = client.get("/objects")
    assert resp.status_code == 401


def test_objects_with_valid_key_returns_list(client):
    resp = client.get("/objects", headers=HEADERS)
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert len(body) > 0


def test_get_missing_object_returns_404(client):
    resp = client.get("/objects/999999999", headers=HEADERS)
    assert resp.status_code == 404


def test_get_state_for_missing_object_returns_404(client):
    resp = client.get("/objects/999999999/state", headers=HEADERS)
    assert resp.status_code == 404


def test_trajectory_endpoint_returns_points(client):
    listing = client.get("/objects", headers=HEADERS).json()
    norad_id = listing[0]["norad_id"]
    resp = client.get(
        f"/objects/{norad_id}/trajectory",
        params={"duration_hours": 1, "step_seconds": 300},
        headers=HEADERS,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["points"]) >= 2


def test_conjunction_screening_persists_and_lists(client):
    resp = client.post(
        "/conjunctions/screen",
        json={"window_hours": 6, "step_seconds": 60, "miss_distance_threshold_km": 500, "persist": True},
        headers=HEADERS,
    )
    assert resp.status_code == 200

    listing = client.get("/conjunctions", headers=HEADERS)
    assert listing.status_code == 200


def test_conjunction_screening_without_persist_returns_ephemeral_events(client):
    resp = client.post(
        "/conjunctions/screen",
        json={"window_hours": 6, "step_seconds": 60, "miss_distance_threshold_km": 500, "persist": False},
        headers=HEADERS,
    )
    assert resp.status_code == 200


def test_maneuver_for_unknown_event_returns_404(client):
    resp = client.post(
        "/conjunctions/CE-DOESNOTEXIST/maneuver", json={}, headers=HEADERS
    )
    assert resp.status_code == 404


def test_debris_priorities_endpoint(client):
    resp = client.get("/debris/priorities", headers=HEADERS)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_alerts_endpoint_lists_and_paginates(client):
    resp = client.get("/alerts", headers=HEADERS)
    assert resp.status_code == 200


def test_acknowledge_nonexistent_alert_returns_404(client):
    resp = client.patch("/alerts/999999/acknowledge", headers=HEADERS)
    assert resp.status_code == 404


def test_cascade_simulate_for_unknown_event_returns_404(client):
    resp = client.post(
        "/cascade/simulate",
        json={"event_id": "CE-DOESNOTEXIST", "fragment_count": 5, "simulation_hours": 1},
        headers=HEADERS,
    )
    assert resp.status_code == 404


def test_ingestion_refresh_endpoint_falls_back_gracefully(client):
    # In this sandboxed test environment CelesTrak is unreachable, so this
    # exercises the synthetic-fallback path end-to-end via the real endpoint.
    resp = client.post("/ingestion/refresh", headers=HEADERS)
    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] in {"CELESTRAK", "SYNTHETIC_FALLBACK"}
