"""
Alert engine.

Generates alerts when conjunction screening surfaces a new HIGH/CRITICAL
severity event, or when miss distance falls below the configurable
"pay attention right now" threshold -- separate from the general
LOW/MODERATE/HIGH/CRITICAL severity classification, which is about relative
risk ranking rather than "should someone look at this immediately".
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import Alert, ConjunctionEvent
from app.schemas.enums import AlertStatus, Severity


def generate_alerts_for_event(db: Session, event: ConjunctionEvent) -> Alert | None:
    settings = get_settings()
    should_alert = (
        event.severity in (Severity.HIGH, Severity.CRITICAL)
        or event.miss_distance_km <= settings.alert_miss_distance_threshold_km
    )
    if not should_alert:
        return None

    title = f"{event.severity.value} conjunction: {event.primary_object_name} / {event.secondary_object_name}"
    message = (
        f"Predicted closest approach at {event.tca.isoformat()} -- "
        f"miss distance {event.miss_distance_km:.3f} km, "
        f"relative velocity {event.relative_velocity_km_s:.3f} km/s, "
        f"risk score {event.risk_score:.2f}."
    )
    alert = Alert(
        conjunction_id=event.id,
        severity=event.severity,
        title=title,
        message=message,
        status=AlertStatus.NEW,
    )
    db.add(alert)
    return alert


def acknowledge_alert(db: Session, alert: Alert) -> Alert:
    from datetime import datetime, timezone
    alert.status = AlertStatus.ACKNOWLEDGED
    alert.acknowledged_at = datetime.now(timezone.utc)
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert
