from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import TrackedObject
from app.services.propagation import Propagator, TrajectoryCache

# Process-wide trajectory cache shared across requests (see propagation.py
# docstring for why this is process-local rather than Redis-backed here).
_shared_cache = TrajectoryCache()


def load_catalog(db: Session, active_only: bool = True) -> list[TrackedObject]:
    stmt = select(TrackedObject)
    if active_only:
        stmt = stmt.where(TrackedObject.active.is_(True))
    return list(db.execute(stmt).scalars().all())


def build_propagator(db: Session, active_only: bool = True) -> Propagator:
    catalog = load_catalog(db, active_only=active_only)
    return Propagator(catalog, cache=_shared_cache)
