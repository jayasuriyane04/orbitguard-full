from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import build_propagator, load_catalog
from app.db.base import get_db
from app.db.models import ConjunctionEvent as ConjunctionEventRow
from app.db.models import TrackedObject as TrackedObjectRow
from app.schemas.analysis import CascadeRequest, CascadeResult, CascadeScenario
from app.security import limiter, require_api_key
from app.services.cascade import simulate_cascade

router = APIRouter(tags=["cascade"])


@router.post("/cascade/simulate", response_model=CascadeResult)
@limiter.limit("5/minute")
def run_cascade_simulation(request: Request, body: CascadeRequest,
                            api_key: str = Depends(require_api_key), db: Session = Depends(get_db)):
    event = db.execute(
        select(ConjunctionEventRow).where(ConjunctionEventRow.event_id == body.event_id)
    ).scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail=f"No conjunction event {body.event_id}")

    primary = db.execute(
        select(TrackedObjectRow).where(TrackedObjectRow.norad_id == event.primary_object_norad_id)
    ).scalar_one_or_none()
    secondary = db.execute(
        select(TrackedObjectRow).where(TrackedObjectRow.norad_id == event.secondary_object_norad_id)
    ).scalar_one_or_none()
    if not primary or not secondary:
        raise HTTPException(status_code=404, detail="Objects for this conjunction are no longer tracked")

    catalog = load_catalog(db)
    propagator = build_propagator(db)

    scenarios = simulate_cascade(
        propagator=propagator, primary=primary, secondary=secondary, tca=event.tca,
        catalog=catalog, fragment_count=body.fragment_count, simulation_hours=body.simulation_hours,
    )

    def to_schema(s) -> CascadeScenario:
        return CascadeScenario(
            label=s.label, fragment_count=s.fragment_count, simulated_hours=s.simulated_hours,
            new_conjunctions=s.new_conjunctions, high_risk_events=s.high_risk_events,
        )

    return CascadeResult(
        event_id=body.event_id,
        without_intervention=to_schema(scenarios["without_intervention"]),
        with_avoidance=to_schema(scenarios["with_avoidance"]),
        with_removal=to_schema(scenarios["with_removal"]),
    )
