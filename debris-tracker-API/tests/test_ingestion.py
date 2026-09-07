from sqlalchemy import select

from app.db.models import TrackedObject as TrackedObjectRow
from app.services.ingestion import ingest_synthetic_fallback, parse_tle


VALID_TLE_LINE1 = "1 25544U 98067A   24001.50000000  .00016717  00000-0  10270-3 0  9004"
VALID_TLE_LINE2 = "2 25544  51.6416 339.4176 0002583  32.2603 327.8879 15.50108106999999"


def test_parse_tle_valid_returns_object():
    result = parse_tle("ISS (ZARYA)", VALID_TLE_LINE1, VALID_TLE_LINE2)
    assert result is not None
    assert result.norad_id == 25544
    assert 0 <= result.inclination_deg <= 180


def test_parse_tle_malformed_returns_none_not_exception():
    result = parse_tle("BAD OBJECT", "not a tle line", "also not a tle line")
    assert result is None


def test_parse_tle_empty_strings_returns_none():
    result = parse_tle("", "", "")
    assert result is None


def test_synthetic_fallback_does_not_duplicate_norad_ids(db_session):
    # db_session fixture already ran ingest_synthetic_fallback once (seed=42)
    ingest_synthetic_fallback(db_session, seed=42)  # run again with same seed

    rows = list(db_session.execute(select(TrackedObjectRow)).scalars().all())
    norad_ids = [r.norad_id for r in rows]
    assert len(norad_ids) == len(set(norad_ids)), "duplicate NORAD IDs found after re-ingestion"


def test_synthetic_fallback_tags_data_source(db_session):
    rows = list(db_session.execute(select(TrackedObjectRow)).scalars().all())
    assert all(r.data_source == "SYNTHETIC" for r in rows)
