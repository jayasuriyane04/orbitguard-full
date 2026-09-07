from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import build_propagator, load_catalog
from app.db.base import get_db
from app.db.models import ConjunctionEvent as ConjunctionEventRow
from app.db.models import ManeuverRecommendation as ManeuverRecommendationRow
from app.db.models import TrackedObject as TrackedObjectRow
from app.schemas.analysis import (
    ConjunctionEventOut,
    ManeuverCandidate,
    ManeuverRequest,
    RiskFactors,
    ScreeningRequest,
)
from app.schemas.enums import Severity
from app.security import limiter, require_api_key
from app.services import conjunction as conjunction_service
from app.services import maneuver as maneuver_service
from app.services.alerts import generate_alerts_for_event

router = APIRouter(tags=["conjunctions"])


def _persist_events(db: Session, results: list) -> list[ConjunctionEventRow]:
    rows = []
    for r in results:
        row = ConjunctionEventRow(
            event_id=r.event_id,
            primary_object_norad_id=r.a.norad_id,
            secondary_object_norad_id=r.b.norad_id,
            primary_object_name=r.a.name,
            secondary_object_name=r.b.name,
            tca=r.tca,
            miss_distance_km=r.miss_distance_km,
            relative_velocity_km_s=r.relative_velocity_km_s,
            risk_score=r.risk_score,
            severity=Severity(r.severity),
            risk_factors_json=json.dumps(r.factors),
        )
        db.add(row)
        db.flush()
        generate_alerts_for_event(db, row)
        rows.append(row)
    db.commit()
    return rows


@router.post("/conjunctions/screen", response_model=list[ConjunctionEventOut])
@limiter.limit("10/minute")
def run_screening(request: Request, screening: ScreeningRequest,
                   api_key: str = Depends(require_api_key), db: Session = Depends(get_db)):
    """Runs a fresh two-stage conjunction screening pass and (by default)
    persists the resulting events, triggering alerts for HIGH/CRITICAL
    results."""
    catalog = load_catalog(db)
    propagator = build_propagator(db)
    results = conjunction_service.screen_conjunctions(
        catalog, propagator,
        window_hours=screening.window_hours,
        step_seconds=screening.step_seconds,
        miss_distance_threshold_km=screening.miss_distance_threshold_km,
    )

    if screening.persist:
        rows = _persist_events(db, results)
        return [_row_to_out(row) for row in rows]

    return [
        ConjunctionEventOut(
            event_id=r.event_id, primary_object=r.a.norad_id, secondary_object=r.b.norad_id,
            primary_object_name=r.a.name, secondary_object_name=r.b.name, tca=r.tca,
            miss_distance_km=r.miss_distance_km, relative_velocity_km_s=r.relative_velocity_km_s,
            risk_score=r.risk_score, severity=Severity(r.severity),
            factors=RiskFactors(**r.factors), created_at=r.tca,
        )
        for r in results
    ]


def _row_to_out(row: ConjunctionEventRow) -> ConjunctionEventOut:
    factors = RiskFactors(**json.loads(row.risk_factors_json)) if row.risk_factors_json else None
    return ConjunctionEventOut(
        event_id=row.event_id, primary_object=row.primary_object_norad_id,
        secondary_object=row.secondary_object_norad_id,
        primary_object_name=row.primary_object_name, secondary_object_name=row.secondary_object_name,
        tca=row.tca, miss_distance_km=row.miss_distance_km,
        relative_velocity_km_s=row.relative_velocity_km_s, risk_score=row.risk_score,
        severity=row.severity, factors=factors, created_at=row.created_at,
    )


@router.get("/conjunctions", response_model=list[ConjunctionEventOut])
@limiter.limit("60/minute")
def list_conjunctions(
    request: Request, api_key: str = Depends(require_api_key), db: Session = Depends(get_db),
    severity: Optional[Severity] = Query(default=None),
    norad_id: Optional[int] = Query(default=None),
    page: int = Query(default=1, ge=1), page_size: int = Query(default=50, ge=1, le=500),
):
    stmt = select(ConjunctionEventRow)
    if severity:
        stmt = stmt.where(ConjunctionEventRow.severity == severity)
    if norad_id:
        stmt = stmt.where(
            (ConjunctionEventRow.primary_object_norad_id == norad_id)
            | (ConjunctionEventRow.secondary_object_norad_id == norad_id)
        )
    stmt = stmt.order_by(ConjunctionEventRow.risk_score.desc())
    rows = list(db.execute(stmt).scalars().all())
    start = (page - 1) * page_size
    return [_row_to_out(r) for r in rows[start:start + page_size]]


@router.get("/conjunctions/{event_id}", response_model=ConjunctionEventOut)
@limiter.limit("60/minute")
def get_conjunction(request: Request, event_id: str,
                     api_key: str = Depends(require_api_key), db: Session = Depends(get_db)):
    row = db.execute(
        select(ConjunctionEventRow).where(ConjunctionEventRow.event_id == event_id)
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail=f"No conjunction event {event_id}")
    return _row_to_out(row)


@router.post("/conjunctions/{event_id}/maneuver", response_model=list[ManeuverCandidate])
@limiter.limit("10/minute")
def generate_maneuver(request: Request, event_id: str, body: ManeuverRequest,
                       api_key: str = Depends(require_api_key), db: Session = Depends(get_db)):
    event = db.execute(
        select(ConjunctionEventRow).where(ConjunctionEventRow.event_id == event_id)
    ).scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail=f"No conjunction event {event_id}")

    primary = db.execute(
        select(TrackedObjectRow).where(TrackedObjectRow.norad_id == event.primary_object_norad_id)
    ).scalar_one_or_none()
    secondary = db.execute(
        select(TrackedObjectRow).where(TrackedObjectRow.norad_id == event.secondary_object_norad_id)
    ).scalar_one_or_none()
    if not primary or not secondary:
        raise HTTPException(status_code=404, detail="Objects for this conjunction are no longer tracked")

    maneuvering, other = (primary, secondary) if primary.maneuverable else (secondary, primary)
    if body.maneuvering_norad_id:
        if body.maneuvering_norad_id == secondary.norad_id:
            maneuvering, other = secondary, primary
        elif body.maneuvering_norad_id == primary.norad_id:
            maneuvering, other = primary, secondary

    if not maneuvering.maneuverable:
        raise HTTPException(
            status_code=422,
            detail="Neither object in this conjunction is maneuverable -- no avoidance burn is possible. "
                   "Consider this object for the debris removal priority list instead.",
        )

    propagator = build_propagator(db)
    candidates = maneuver_service.plan_maneuvers(
        propagator=propagator, maneuvering_object=maneuvering, other_object=other,
        tca=event.tca, original_miss_distance_km=event.miss_distance_km,
        original_risk_score=event.risk_score,
        miss_distance_threshold_km=max(event.miss_distance_km * 3, 25.0),
        delta_v_candidates_m_s=body.delta_v_candidates_m_s,
    )

    if not candidates:
        raise HTTPException(
            status_code=422,
            detail="No feasible burn window found before TCA (event may already be too close).",
        )

    # persist top candidates for later retrieval/audit
    for c in candidates[:10]:
        db.add(ManeuverRecommendationRow(
            conjunction_id=event.id, maneuvering_object_norad_id=maneuvering.norad_id,
            direction=c.direction, delta_v_m_s=c.delta_v_m_s,
            execute_before_tca_minutes=c.execute_before_tca_minutes,
            original_miss_distance_km=c.original_miss_distance_km,
            predicted_miss_distance_km=c.predicted_miss_distance_km,
            original_risk_score=c.original_risk_score,
            predicted_risk_score=c.predicted_risk_score,
        ))
    db.commit()

    return [ManeuverCandidate(**vars(c)) for c in candidates[:10]]
