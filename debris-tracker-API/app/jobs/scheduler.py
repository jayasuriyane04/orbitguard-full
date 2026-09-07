"""
Lightweight background jobs using APScheduler -- deliberately not a
Celery/Redis setup, which would be overkill for a hackathon-scale MVP with
a single API process. If ORBITGUARD needs to scale to multiple workers or
truly long-running jobs later, swap this module for a Celery/Redis
architecture without touching the service layer it calls into.
"""
from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app.api.deps import build_propagator, load_catalog
from app.core.config import get_settings
from app.db.base import SessionLocal

logger = logging.getLogger("orbitguard.jobs")

_scheduler: BackgroundScheduler | None = None


def _run_ingestion_refresh() -> None:
    from app.services.ingestion import ingest_catalog

    db = SessionLocal()
    try:
        result = ingest_catalog(db)
        logger.info("Scheduled ingestion refresh: %s", result)
    except Exception:  # noqa: BLE001
        logger.exception("Scheduled ingestion refresh failed")
    finally:
        db.close()


def _run_screening_and_alerts() -> None:
    """Re-runs conjunction screening + alert generation on the current
    catalog. Trajectory cache entries are naturally refreshed as a side
    effect of the new propagation calls this makes."""
    import json

    from app.db.models import ConjunctionEvent as ConjunctionEventRow
    from app.schemas.enums import Severity
    from app.services import conjunction as conjunction_service
    from app.services.alerts import generate_alerts_for_event

    settings = get_settings()
    db = SessionLocal()
    try:
        catalog = load_catalog(db)
        propagator = build_propagator(db)
        results = conjunction_service.screen_conjunctions(
            catalog, propagator,
            window_hours=settings.default_window_hours,
            step_seconds=settings.default_step_seconds,
            miss_distance_threshold_km=settings.default_miss_distance_km,
        )
        new_alerts = 0
        for r in results:
            row = ConjunctionEventRow(
                event_id=r.event_id, primary_object_norad_id=r.a.norad_id,
                secondary_object_norad_id=r.b.norad_id, primary_object_name=r.a.name,
                secondary_object_name=r.b.name, tca=r.tca, miss_distance_km=r.miss_distance_km,
                relative_velocity_km_s=r.relative_velocity_km_s, risk_score=r.risk_score,
                severity=Severity(r.severity), risk_factors_json=json.dumps(r.factors),
            )
            db.add(row)
            db.flush()
            if generate_alerts_for_event(db, row):
                new_alerts += 1
        db.commit()
        logger.info("Scheduled screening: %d events, %d new alerts", len(results), new_alerts)
    except Exception:  # noqa: BLE001
        logger.exception("Scheduled screening refresh failed")
        db.rollback()
    finally:
        db.close()


def start_scheduler() -> BackgroundScheduler | None:
    global _scheduler
    settings = get_settings()
    if not settings.enable_background_jobs:
        logger.info("Background jobs disabled (ORBITGUARD_ENABLE_JOBS=false)")
        return None

    _scheduler = BackgroundScheduler(timezone="UTC")
    _scheduler.add_job(
        _run_ingestion_refresh, "interval",
        minutes=settings.ingestion_refresh_minutes, id="ingestion_refresh",
    )
    _scheduler.add_job(
        _run_screening_and_alerts, "interval",
        minutes=settings.screening_refresh_minutes, id="screening_refresh",
    )
    _scheduler.start()
    logger.info(
        "Background scheduler started (ingestion every %s min, screening every %s min)",
        settings.ingestion_refresh_minutes, settings.screening_refresh_minutes,
    )
    return _scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
