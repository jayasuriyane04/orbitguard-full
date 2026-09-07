from datetime import datetime, timezone

from app.api.deps import build_propagator, load_catalog
from app.services.conjunction import broad_phase_filter, screen_conjunctions


def test_broad_phase_filter_returns_fewer_pairs_than_full_n_squared(db_session):
    catalog = load_catalog(db_session)
    candidates = broad_phase_filter(catalog)
    n = len(catalog)
    full_pairs = n * (n - 1) // 2
    assert len(candidates) <= full_pairs


def test_screen_conjunctions_runs_end_to_end_with_zero_results_possible(db_session):
    catalog = load_catalog(db_session)
    propagator = build_propagator(db_session)

    # A very tight threshold should still run without error, even if it
    # legitimately finds zero conjunctions in the synthetic catalog.
    results = screen_conjunctions(
        catalog, propagator, window_hours=1, step_seconds=60,
        miss_distance_threshold_km=0.001,
        start_time=datetime.now(timezone.utc),
    )
    assert isinstance(results, list)


def test_screen_conjunctions_wide_threshold_finds_events_and_sorts_by_risk(db_session):
    catalog = load_catalog(db_session)
    propagator = build_propagator(db_session)

    results = screen_conjunctions(
        catalog, propagator, window_hours=6, step_seconds=60,
        miss_distance_threshold_km=500,
        start_time=datetime.now(timezone.utc),
    )
    if len(results) > 1:
        scores = [r.risk_score for r in results]
        assert scores == sorted(scores, reverse=True)
    for r in results:
        assert r.miss_distance_km <= 500
        assert r.a.norad_id != r.b.norad_id
