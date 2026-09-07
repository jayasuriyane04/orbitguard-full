from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import build_propagator, load_catalog
from app.db.base import get_db
from app.db.models import TrackedObject as TrackedObjectRow
from app.schemas.enums import ObjectType
from app.schemas.objects import (
    StateVectorOut,
    TrackedObjectOut,
    TrajectoryOut,
    TrajectoryPoint,
)
from app.security import limiter, require_api_key

router = APIRouter(tags=["objects"])


@router.get("/objects", response_model=list[TrackedObjectOut])
@limiter.limit("60/minute")
def list_objects(
    request: Request,
    api_key: str = Depends(require_api_key),
    db: Session = Depends(get_db),
    object_type: Optional[ObjectType] = Query(default=None),
    maneuverable: Optional[bool] = Query(default=None),
    min_altitude_km: Optional[float] = Query(default=None),
    max_altitude_km: Optional[float] = Query(default=None),
    name: Optional[str] = Query(default=None, description="Case-insensitive substring match"),
    norad_id: Optional[int] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
):
    stmt = select(TrackedObjectRow).where(TrackedObjectRow.active.is_(True))
    if object_type:
        stmt = stmt.where(TrackedObjectRow.object_type == object_type)
    if maneuverable is not None:
        stmt = stmt.where(TrackedObjectRow.maneuverable == maneuverable)
    if name:
        stmt = stmt.where(TrackedObjectRow.name.ilike(f"%{name}%"))
    if norad_id:
        stmt = stmt.where(TrackedObjectRow.norad_id == norad_id)

    rows = list(db.execute(stmt).scalars().all())

    if min_altitude_km is not None or max_altitude_km is not None:
        import math
        mu = 398600.4418

        def approx_alt(o: TrackedObjectRow) -> float:
            n_rad_s = o.mean_motion_rev_per_day * 2 * math.pi / 86400.0
            a_km = (mu / (n_rad_s ** 2)) ** (1 / 3)
            return a_km - 6378.137

        rows = [r for r in rows
                if (min_altitude_km is None or approx_alt(r) >= min_altitude_km)
                and (max_altitude_km is None or approx_alt(r) <= max_altitude_km)]

    total = len(rows)
    start = (page - 1) * page_size
    page_rows = rows[start:start + page_size]
    return [TrackedObjectOut.from_orm_row(r) for r in page_rows]


@router.get("/objects/{norad_id}", response_model=TrackedObjectOut)
@limiter.limit("60/minute")
def get_object(request: Request, norad_id: int,
                api_key: str = Depends(require_api_key), db: Session = Depends(get_db)):
    row = db.execute(
        select(TrackedObjectRow).where(TrackedObjectRow.norad_id == norad_id)
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail=f"No tracked object with norad_id {norad_id}")
    return TrackedObjectOut.from_orm_row(row)


@router.get("/objects/{norad_id}/state", response_model=StateVectorOut)
@limiter.limit("60/minute")
def get_state(request: Request, norad_id: int, at: Optional[datetime] = None,
              api_key: str = Depends(require_api_key), db: Session = Depends(get_db)):
    when = at or datetime.now(timezone.utc)
    propagator = build_propagator(db)
    try:
        s = propagator.state_at(norad_id, when)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"No tracked object with norad_id {norad_id}")
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return StateVectorOut(
        norad_id=s.norad_id, timestamp=s.timestamp,
        x_km=s.position_km[0], y_km=s.position_km[1], z_km=s.position_km[2],
        vx_km_s=s.velocity_km_s[0], vy_km_s=s.velocity_km_s[1], vz_km_s=s.velocity_km_s[2],
        altitude_km=s.altitude_km, latitude_deg=s.latitude_deg, longitude_deg=s.longitude_deg,
    )


@router.get("/objects/{norad_id}/trajectory", response_model=TrajectoryOut)
@limiter.limit("30/minute")
def get_trajectory(
    request: Request, norad_id: int,
    duration_hours: float = Query(2.0, gt=0, le=72),
    step_seconds: float = Query(60.0, gt=0, le=600),
    start: Optional[datetime] = None,
    api_key: str = Depends(require_api_key), db: Session = Depends(get_db),
):
    start_time = start or datetime.now(timezone.utc)
    propagator = build_propagator(db)
    try:
        states = propagator.trajectory(
            norad_id, start_time, timedelta(hours=duration_hours), timedelta(seconds=step_seconds)
        )
    except KeyError:
        raise HTTPException(status_code=404, detail=f"No tracked object with norad_id {norad_id}")
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    points = [
        TrajectoryPoint(
            timestamp=s.timestamp, x_km=s.position_km[0], y_km=s.position_km[1], z_km=s.position_km[2],
            vx_km_s=s.velocity_km_s[0], vy_km_s=s.velocity_km_s[1], vz_km_s=s.velocity_km_s[2],
            latitude_deg=s.latitude_deg, longitude_deg=s.longitude_deg, altitude_km=s.altitude_km,
        )
        for s in states
    ]
    return TrajectoryOut(
        norad_id=norad_id, start=start_time, end=start_time + timedelta(hours=duration_hours),
        step_seconds=step_seconds, points=points,
    )
