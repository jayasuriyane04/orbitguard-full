from datetime import datetime, timedelta, timezone

from app.api.deps import build_propagator, load_catalog
from app.services.maneuver import plan_maneuvers


def test_maneuver_planner_skips_non_maneuverable_primary(db_session):
    catalog = load_catalog(db_session)
    debris = [o for o in catalog if not o.maneuverable][0]
    other = [o for o in catalog if o.norad_id != debris.norad_id][0]
    propagator = build_propagator(db_session)

    candidates = plan_maneuvers(
        propagator=propagator, maneuvering_object=debris, other_object=other,
        tca=datetime.now(timezone.utc) + timedelta(hours=2),
        original_miss_distance_km=1.0, original_risk_score=0.9,
        miss_distance_threshold_km=25.0,
    )
    assert candidates == []


def test_maneuver_planner_produces_ranked_candidates_for_maneuverable_object(db_session):
    catalog = load_catalog(db_session)
    sat = [o for o in catalog if o.maneuverable][0]
    other = [o for o in catalog if o.norad_id != sat.norad_id][0]
    propagator = build_propagator(db_session)
    tca = datetime.now(timezone.utc) + timedelta(hours=3)

    candidates = plan_maneuvers(
        propagator=propagator, maneuvering_object=sat, other_object=other, tca=tca,
        original_miss_distance_km=1.0, original_risk_score=0.9,
        miss_distance_threshold_km=25.0,
        delta_v_candidates_m_s=[0.1, 0.5],
    )
    assert len(candidates) > 0
    risk_scores = [c.predicted_risk_score for c in candidates]
    assert risk_scores == sorted(risk_scores)
    for c in candidates:
        assert c.delta_v_m_s > 0
        assert c.execute_before_tca_minutes > 0
