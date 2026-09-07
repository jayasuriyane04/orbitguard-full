"""
Orbital data ingestion.

Primary source: CelesTrak's GP (General Perturbations) TLE feed, which is
free, public, and requires no API key -- a good fit for a hackathon-grade
SSA demo. Each fetch upserts objects into the database keyed on NORAD ID
(never duplicated) and stamps a last-update time.

If CelesTrak is unreachable (offline demo, network policy, rate limit),
ingestion falls back to the existing synthetic catalog generator so the
rest of the pipeline (propagation, screening, dashboard) always has data
to work with. The fallback is explicit and recorded via `data_source`,
never silently mixed with real data.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

import requests
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import TrackedObject
from app.schemas.enums import DataSource, ObjectType
from app.services import legacy_catalog

logger = logging.getLogger("orbitguard.ingestion")

# CelesTrak GROUP values covering the three object categories we track.
# "active" satellites, upper-stage rocket bodies, and a representative
# fragmentation-debris group (fetched in addition to whatever the caller
# requests) so the catalog isn't satellite-only.
CELESTRAK_GROUPS: dict[str, ObjectType] = {
    "active": ObjectType.ACTIVE_SATELLITE,
    "cosmos-2251-debris": ObjectType.DEBRIS,
    "iridium-33-debris": ObjectType.DEBRIS,
}


@dataclass
class ParsedTLE:
    norad_id: int
    name: str
    line1: str
    line2: str
    epoch: datetime
    inclination_deg: float
    eccentricity: float
    raan_deg: float
    arg_perigee_deg: float
    mean_anomaly_deg: float
    mean_motion_rev_per_day: float
    bstar: float


def parse_tle(name: str, line1: str, line2: str) -> ParsedTLE | None:
    """Parse a 3-line TLE block using sgp4's own validated parser.

    Returns None (rather than raising) for malformed input so a single bad
    record from a large feed doesn't abort the whole ingestion run.
    """
    try:
        from sgp4.api import Satrec
        from sgp4.conveniences import sat_epoch_datetime

        sat = Satrec.twoline2rv(line1, line2)
        epoch = sat_epoch_datetime(sat)
        mean_motion_rev_per_day = sat.no_kozai * 1440.0 / (2 * 3.141592653589793)
        return ParsedTLE(
            norad_id=sat.satnum,
            name=name.strip(),
            line1=line1.strip(),
            line2=line2.strip(),
            epoch=epoch if epoch.tzinfo else epoch.replace(tzinfo=timezone.utc),
            inclination_deg=sat.inclo * 180.0 / 3.141592653589793,
            eccentricity=sat.ecco,
            raan_deg=sat.nodeo * 180.0 / 3.141592653589793,
            arg_perigee_deg=sat.argpo * 180.0 / 3.141592653589793,
            mean_anomaly_deg=sat.mo * 180.0 / 3.141592653589793,
            mean_motion_rev_per_day=mean_motion_rev_per_day,
            bstar=sat.bstar,
        )
    except Exception as exc:  # noqa: BLE001 - defensive: never let bad input crash ingestion
        logger.warning("Skipping malformed TLE for %r: %s", name, exc)
        return None


def _fetch_group_tles(group: str, timeout: float) -> list[str]:
    settings = get_settings()
    url = f"{settings.celestrak_base_url}?GROUP={group}&FORMAT=tle"
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    lines = [ln.rstrip("\r\n") for ln in resp.text.splitlines() if ln.strip()]
    return lines


def fetch_celestrak_tles(timeout: float | None = None) -> list[tuple[ParsedTLE, ObjectType]]:
    """Fetch and parse TLEs for each configured CelesTrak group.

    Raises the underlying network/HTTP exception on failure so the caller
    (ingest_catalog) can decide whether to fall back to synthetic data.
    """
    settings = get_settings()
    timeout = timeout or settings.ingestion_timeout_seconds
    results: list[tuple[ParsedTLE, ObjectType]] = []

    for group, object_type in CELESTRAK_GROUPS.items():
        lines = _fetch_group_tles(group, timeout)
        i = 0
        while i + 2 < len(lines) + 1 and i + 2 <= len(lines):
            if i + 2 > len(lines) - 1 and i + 2 != len(lines):
                break
            name, l1, l2 = lines[i], lines[i + 1], lines[i + 2]
            parsed = parse_tle(name, l1, l2)
            if parsed:
                results.append((parsed, object_type))
            i += 3

    if not results:
        raise RuntimeError("CelesTrak returned no parseable TLEs")
    return results


def _upsert(db: Session, parsed: ParsedTLE, object_type: ObjectType,
            source: DataSource, maneuverable: bool | None = None) -> tuple[bool, bool]:
    """Insert or update a TrackedObject by NORAD ID. Returns (created, updated)."""
    existing = db.execute(
        select(TrackedObject).where(TrackedObject.norad_id == parsed.norad_id)
    ).scalar_one_or_none()

    is_maneuverable = (
        maneuverable if maneuverable is not None else (object_type == ObjectType.ACTIVE_SATELLITE)
    )

    if existing is None:
        db.add(TrackedObject(
            norad_id=parsed.norad_id,
            name=parsed.name,
            object_type=object_type,
            tle_line1=parsed.line1,
            tle_line2=parsed.line2,
            epoch=parsed.epoch,
            inclination_deg=parsed.inclination_deg,
            eccentricity=parsed.eccentricity,
            raan_deg=parsed.raan_deg,
            arg_perigee_deg=parsed.arg_perigee_deg,
            mean_anomaly_deg=parsed.mean_anomaly_deg,
            mean_motion_rev_per_day=parsed.mean_motion_rev_per_day,
            bstar=parsed.bstar,
            maneuverable=is_maneuverable,
            active=True,
            data_source=source.value,
        ))
        return True, False

    # Only update if this TLE epoch is newer -- avoid clobbering fresher data
    # with a stale re-fetch. SQLite drops tzinfo on round-trip, so normalize
    # both sides to naive-UTC-equivalent before comparing.
    existing_epoch = existing.epoch if existing.epoch.tzinfo else existing.epoch.replace(tzinfo=timezone.utc)
    parsed_epoch = parsed.epoch if parsed.epoch.tzinfo else parsed.epoch.replace(tzinfo=timezone.utc)
    if parsed_epoch >= existing_epoch:
        existing.name = parsed.name
        existing.tle_line1 = parsed.line1
        existing.tle_line2 = parsed.line2
        existing.epoch = parsed.epoch
        existing.inclination_deg = parsed.inclination_deg
        existing.eccentricity = parsed.eccentricity
        existing.raan_deg = parsed.raan_deg
        existing.arg_perigee_deg = parsed.arg_perigee_deg
        existing.mean_anomaly_deg = parsed.mean_anomaly_deg
        existing.mean_motion_rev_per_day = parsed.mean_motion_rev_per_day
        existing.bstar = parsed.bstar
        existing.data_source = source.value
        return False, True
    return False, False


def ingest_synthetic_fallback(db: Session, seed: int | None = 42) -> dict:
    """Populate (or refresh) the catalog from the deterministic synthetic
    generator that already existed in this repo, tagging every row as
    SYNTHETIC so it's never confused with real tracking data.
    """
    catalog = legacy_catalog.generate_catalog(seed=seed)
    created = updated = 0
    for obj in catalog:
        parsed = ParsedTLE(
            norad_id=obj.norad_id,
            name=obj.name,
            line1="",
            line2="",
            epoch=obj.epoch,
            inclination_deg=obj.elements.inclination_deg,
            eccentricity=obj.elements.eccentricity,
            raan_deg=obj.elements.raan_deg,
            arg_perigee_deg=obj.elements.arg_perigee_deg,
            mean_anomaly_deg=obj.elements.mean_anomaly_deg,
            mean_motion_rev_per_day=obj.elements.mean_motion_rev_per_day,
            bstar=obj.elements.bstar,
        )
        object_type = {
            "satellite": ObjectType.ACTIVE_SATELLITE,
            "rocket_body": ObjectType.ROCKET_BODY,
            "debris": ObjectType.DEBRIS,
        }.get(obj.object_type.value, ObjectType.UNKNOWN)
        was_created, was_updated = _upsert(
            db, parsed, object_type, DataSource.SYNTHETIC, maneuverable=obj.maneuverable
        )
        created += was_created
        updated += was_updated
    db.commit()
    return {"fetched": len(catalog), "created": created, "updated": updated, "skipped_invalid": 0}


def ingest_catalog(db: Session) -> dict:
    """Main entry point used by the /ingestion/refresh endpoint and the
    scheduled background job. Tries CelesTrak first; falls back to the
    synthetic generator only if real ingestion fails and the fallback is
    enabled in settings.
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)

    try:
        parsed_records = fetch_celestrak_tles()
        created = updated = skipped = 0
        for parsed, object_type in parsed_records:
            was_created, was_updated = _upsert(db, parsed, object_type, DataSource.CELESTRAK)
            created += was_created
            updated += was_updated
        db.commit()
        return {
            "source": "CELESTRAK",
            "fetched": len(parsed_records),
            "created": created,
            "updated": updated,
            "skipped_invalid": skipped,
            "used_fallback": False,
            "last_update": now,
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("CelesTrak ingestion failed (%s); falling back to synthetic catalog", exc)
        if not settings.use_synthetic_fallback:
            raise
        stats = ingest_synthetic_fallback(db)
        return {
            "source": "SYNTHETIC_FALLBACK",
            "used_fallback": True,
            "last_update": now,
            **stats,
        }
