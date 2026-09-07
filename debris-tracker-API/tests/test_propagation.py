from datetime import datetime, timedelta, timezone

from app.api.deps import build_propagator, load_catalog


def test_state_at_returns_valid_geodetic(db_session):
    catalog = load_catalog(db_session)
    propagator = build_propagator(db_session)
    obj = catalog[0]

    state = propagator.state_at(obj.norad_id, datetime.now(timezone.utc))

    assert state.norad_id == obj.norad_id
    assert -90 <= state.latitude_deg <= 90
    assert -180 <= state.longitude_deg <= 180
    assert state.altitude_km > 0


def test_state_at_unknown_norad_id_raises_keyerror(db_session):
    propagator = build_propagator(db_session)
    try:
        propagator.state_at(999999999, datetime.now(timezone.utc))
        assert False, "expected KeyError"
    except KeyError:
        pass


def test_trajectory_returns_expected_point_count(db_session):
    catalog = load_catalog(db_session)
    propagator = build_propagator(db_session)
    obj = catalog[0]
    now = datetime.now(timezone.utc)

    states = propagator.trajectory(obj.norad_id, now, timedelta(hours=1), timedelta(minutes=10))

    assert len(states) == 7  # 60 min / 10 min steps + 1
    timestamps = [s.timestamp for s in states]
    assert timestamps == sorted(timestamps)


def test_cache_returns_identical_state_for_repeated_query(db_session):
    catalog = load_catalog(db_session)
    propagator = build_propagator(db_session)
    obj = catalog[0]
    when = datetime.now(timezone.utc)

    first = propagator.state_at(obj.norad_id, when)
    second = propagator.state_at(obj.norad_id, when)

    assert first.position_km == second.position_km
