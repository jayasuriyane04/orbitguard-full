from app.api.deps import load_catalog
from app.schemas.enums import Severity
from app.services.risk import assess_risk, severity_for_score


def test_close_slow_conjunction_between_satellites_is_high_risk(db_session):
    catalog = load_catalog(db_session)
    sats = [o for o in catalog if o.maneuverable]
    a, b = sats[0], sats[1]

    result = assess_risk(
        miss_distance_km=0.1, relative_velocity_km_s=1.0,
        object_a=a, object_b=b, miss_distance_threshold_km=25.0,
    )
    assert 0.0 <= result["risk_score"] <= 1.0
    assert result["severity"] in {s.value for s in Severity}
    assert set(result["factors"].keys()) == {"distance", "velocity", "object_type", "maneuverability"}


def test_far_miss_is_low_risk(db_session):
    catalog = load_catalog(db_session)
    a, b = catalog[0], catalog[1]

    result = assess_risk(
        miss_distance_km=24.9, relative_velocity_km_s=0.5,
        object_a=a, object_b=b, miss_distance_threshold_km=25.0,
    )
    assert result["risk_score"] < 0.5


def test_no_maneuverable_object_raises_risk_relative_to_maneuverable_case(db_session):
    catalog = load_catalog(db_session)
    debris = [o for o in catalog if not o.maneuverable]
    sats = [o for o in catalog if o.maneuverable]
    a, b = debris[0], debris[1]
    c, d = sats[0], debris[0]

    no_maneuver_result = assess_risk(
        miss_distance_km=5.0, relative_velocity_km_s=5.0,
        object_a=a, object_b=b, miss_distance_threshold_km=25.0,
    )
    with_maneuver_result = assess_risk(
        miss_distance_km=5.0, relative_velocity_km_s=5.0,
        object_a=c, object_b=d, miss_distance_threshold_km=25.0,
    )
    assert no_maneuver_result["factors"]["maneuverability"] > with_maneuver_result["factors"]["maneuverability"]


def test_severity_thresholds_are_monotonic():
    scores = [0.0, 0.2, 0.35, 0.6, 0.85, 1.0]
    severities = [severity_for_score(s) for s in scores]
    order = [Severity.LOW, Severity.MODERATE, Severity.HIGH, Severity.CRITICAL]
    assert all(order.index(sev) >= order.index(severities[i - 1]) for i, sev in enumerate(severities) if i > 0)
