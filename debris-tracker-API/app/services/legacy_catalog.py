"""
Generates a tracked-object catalog from Keplerian elements.

In production this module would be replaced by an ingestion job that pulls
state vectors / TLEs from a real data provider (e.g. an 18th Space Defense
Squadron feed) on a schedule, validates them, and upserts into a database.
Here we synthesize a realistic population directly from orbital element
distributions so the rest of the pipeline (propagation, screening, API)
can be exercised end-to-end without an external dependency.
"""
import math
import random
from datetime import datetime, timezone

from app.models import TrackedObject, OrbitalElements, ObjectType

EARTH_RADIUS_KM = 6378.137
MU_EARTH = 398600.4418  # km^3/s^2


def mean_motion_for_altitude(altitude_km: float) -> float:
    """Revolutions per day for a near-circular orbit at given altitude."""
    r = EARTH_RADIUS_KM + altitude_km
    period_s = 2 * math.pi * math.sqrt(r ** 3 / MU_EARTH)
    return 86400.0 / period_s


def _make_object(norad_id: int, name: str, object_type: ObjectType,
                  altitude_km: float, inclination_deg: float,
                  eccentricity: float, rcs_m2: float,
                  maneuverable: bool, epoch: datetime) -> TrackedObject:
    elements = OrbitalElements(
        inclination_deg=inclination_deg,
        raan_deg=random.uniform(0, 360),
        eccentricity=eccentricity,
        arg_perigee_deg=random.uniform(0, 360),
        mean_anomaly_deg=random.uniform(0, 360),
        mean_motion_rev_per_day=mean_motion_for_altitude(altitude_km),
        bstar=0.0001 if object_type != ObjectType.satellite else 0.00001,
    )
    return TrackedObject(
        norad_id=norad_id,
        name=name,
        object_type=object_type,
        rcs_m2=rcs_m2,
        maneuverable=maneuverable,
        elements=elements,
        epoch=epoch,
    )


def generate_catalog(seed: int | None = None) -> list[TrackedObject]:
    if seed is not None:
        random.seed(seed)

    epoch = datetime.now(timezone.utc)
    catalog: list[TrackedObject] = []
    norad_id = 44000

    sat_prefixes = ["ARGUS", "VELA", "MERIDIAN", "HALCYON", "PRISM", "ECHELON", "NOMAD", "SENTRY"]
    for i, prefix in enumerate(sat_prefixes):
        altitude = random.uniform(400, 1400)
        catalog.append(_make_object(
            norad_id=norad_id, name=f"{prefix}-{100 + i}",
            object_type=ObjectType.satellite,
            altitude_km=altitude,
            inclination_deg=random.uniform(0, 98),
            eccentricity=random.uniform(0.0001, 0.003),
            rcs_m2=random.uniform(2, 8),
            maneuverable=True,
            epoch=epoch,
        ))
        norad_id += 1

    rb_count = 5
    for i in range(rb_count):
        altitude = random.uniform(500, 1600)
        catalog.append(_make_object(
            norad_id=norad_id, name=f"SL-STAGE-{500 + i}",
            object_type=ObjectType.rocket_body,
            altitude_km=altitude,
            inclination_deg=random.uniform(0, 105),
            eccentricity=random.uniform(0.001, 0.02),
            rcs_m2=random.uniform(8, 20),
            maneuverable=False,
            epoch=epoch,
        ))
        norad_id += 1

    debris_count = 22
    for i in range(debris_count):
        altitude = random.uniform(350, 1800)
        catalog.append(_make_object(
            norad_id=norad_id, name=f"FRAG-{2000 + i * 3}",
            object_type=ObjectType.debris,
            altitude_km=altitude,
            inclination_deg=random.uniform(0, 170),
            eccentricity=random.uniform(0.0005, 0.05),
            rcs_m2=random.uniform(0.02, 1.2),
            maneuverable=False,
            epoch=epoch,
        ))
        norad_id += 1

    return catalog
