"""
ORBITGUARD -- AI-assisted space debris monitoring, collision prediction and
mitigation decision-support platform.

This file wires together the persistent catalog, the analysis services, and
the API routers. The original debris-tracker-API's security (API-key auth)
and rate limiting are kept as-is; conjunction screening, propagation, and
the catalog itself have been upgraded to the versions in app/services/.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.api import alerts, cascade, conjunctions, debris, ingestion, objects
from app.core.config import get_settings
from app.db.base import SessionLocal, get_db, init_db
from app.db.models import TrackedObject as TrackedObjectRow
from app.jobs.scheduler import start_scheduler, stop_scheduler
from app.security import limiter
from app.services.ingestion import ingest_catalog

logging.basicConfig(level=logging.INFO)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()

    # Seed the catalog on first boot only, so restarts don't re-fetch/re-seed
    # every time. Use POST /ingestion/refresh to force a refresh later.
    db = SessionLocal()
    try:
        count = db.execute(select(func.count()).select_from(TrackedObjectRow)).scalar_one()
        if count == 0:
            logging.info("Empty catalog detected -- running initial ingestion")
            ingest_catalog(db)
    finally:
        db.close()

    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title="ORBITGUARD",
    description=(
        "AI-Assisted Space Debris Monitoring, Collision Prediction and "
        "Mitigation Decision-Support Platform. DETECT -> TRACK -> PREDICT -> "
        "ASSESS -> ALERT -> MITIGATE -> PRIORITIZE."
    ),
    version=settings.app_version,
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["X-API-Key", "Content-Type"],
)

app.include_router(objects.router)
app.include_router(ingestion.router)
app.include_router(conjunctions.router)
app.include_router(debris.router)
app.include_router(cascade.router)
app.include_router(alerts.router)


@app.get("/health")
def health(db: Session = Depends(get_db)):
    count = db.execute(select(func.count()).select_from(TrackedObjectRow)).scalar_one()
    return {"status": "ok", "objects_tracked": count, "version": settings.app_version}
